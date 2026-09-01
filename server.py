#!/usr/bin/env python3
"""Servidor local da interface web da carteira.

Uso:
    python server.py               # http://127.0.0.1:8765
    python server.py --porta 9000
    python server.py --sem-navegador

Usa apenas a biblioteca padrão — não exige Flask nem qualquer framework.
Ouve somente em 127.0.0.1: a interface não fica exposta na rede.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from core import ai_insights, notifier, portfolio, report, runner  # noqa: E402
from core.paths import WEB_DIR  # noqa: E402

# Uma análise por vez: a chamada à IA é cara e demorada.
_lock_analise = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    server_version = "PortfolioAnalyzer/1.0"

    # ── infraestrutura ────────────────────────

    def log_message(self, formato, *args):
        if self.path.startswith("/api/"):
            print(f"  {self.command} {self.path} → {args[1] if len(args) > 1 else ''}")

    def _json(self, dados, status: int = 200) -> None:
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _erro(self, mensagem: str, status: int = 400) -> None:
        self._json({"erro": mensagem}, status)

    def _corpo(self) -> dict:
        tamanho = int(self.headers.get("Content-Length") or 0)
        if not tamanho:
            return {}
        try:
            return json.loads(self.rfile.read(tamanho).decode("utf-8"))
        except json.JSONDecodeError:
            raise ValueError("Corpo da requisição não é JSON válido.") from None

    def _arquivo(self, nome: str) -> None:
        caminho = (WEB_DIR / nome).resolve()
        if not caminho.is_file() or WEB_DIR.resolve() not in caminho.parents:
            self.send_error(404, "Arquivo não encontrado")
            return
        tipo = mimetypes.guess_type(str(caminho))[0] or "application/octet-stream"
        dados = caminho.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{tipo}; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(dados)

    # ── rotas ─────────────────────────────────

    def do_GET(self):  # noqa: N802
        rota = urlparse(self.path)
        caminho, query = rota.path, parse_qs(rota.query)

        if caminho in ("/", "/index.html"):
            return self._arquivo("index.html")
        if caminho.startswith("/static/"):
            return self._arquivo(caminho[len("/static/"):])

        try:
            if caminho == "/api/carteira":
                return self._json(portfolio.load())

            if caminho == "/api/analise":
                ultima = runner.ultima_analise()
                return self._json(ultima or {"vazio": True})

            if caminho == "/api/historico":
                limite = int(query.get("limite", ["60"])[0])
                return self._json({"serie": runner.historico(limite)})

            if caminho == "/api/status":
                ia_ok, ia_motivo = ai_insights.disponivel()
                return self._json({
                    "ia_disponivel": ia_ok,
                    "ia_motivo": ia_motivo,
                    "telegram_configurado": notifier.configurado(),
                    "modelo": ai_insights.MODELO,
                })
        except Exception as exc:
            return self._erro(f"Erro interno: {exc}", 500)

        self.send_error(404, "Rota não encontrada")

    def do_POST(self):  # noqa: N802
        rota = urlparse(self.path)
        caminho, query = rota.path, parse_qs(rota.query)

        try:
            corpo = self._corpo()
        except ValueError as exc:
            return self._erro(str(exc))

        try:
            if caminho == "/api/posicoes":
                return self._json(portfolio.adicionar(corpo), 201)

            if caminho == "/api/config":
                return self._json(portfolio.atualizar_config(corpo))

            if caminho == "/api/analise":
                usar_ia = query.get("ia", ["1"])[0] != "0"
                if not _lock_analise.acquire(blocking=False):
                    return self._erro("Já existe uma análise em andamento.", 409)
                try:
                    resultado = runner.executar(usar_ia=usar_ia)
                finally:
                    _lock_analise.release()
                return self._json(resultado)

            if caminho == "/api/telegram":
                ultima = runner.ultima_analise()
                if not ultima:
                    return self._erro("Rode uma análise antes de enviar ao Telegram.")
                notifier.enviar(report.telegram(
                    ultima["snapshot"], ultima.get("ia"), ultima.get("fundamentos")
                ))
                return self._json({"ok": True})

            if caminho == "/api/telegram/testar":
                return self._json({"ok": True, "bot": notifier.testar()})

        except portfolio.ValidacaoError as exc:
            return self._erro(str(exc), 422)
        except Exception as exc:
            return self._erro(f"Erro interno: {exc}", 500)

        self.send_error(404, "Rota não encontrada")

    def do_PUT(self):  # noqa: N802
        caminho = urlparse(self.path).path
        try:
            corpo = self._corpo()
        except ValueError as exc:
            return self._erro(str(exc))

        if caminho.startswith("/api/posicoes/"):
            pos_id = caminho[len("/api/posicoes/"):]
            try:
                return self._json(portfolio.atualizar(pos_id, corpo))
            except portfolio.ValidacaoError as exc:
                return self._erro(str(exc), 422)
            except Exception as exc:
                return self._erro(f"Erro interno: {exc}", 500)

        self.send_error(404, "Rota não encontrada")

    def do_DELETE(self):  # noqa: N802
        caminho = urlparse(self.path).path
        if caminho.startswith("/api/posicoes/"):
            pos_id = caminho[len("/api/posicoes/"):]
            try:
                portfolio.remover(pos_id)
                return self._json({"ok": True})
            except portfolio.ValidacaoError as exc:
                return self._erro(str(exc), 404)
            except Exception as exc:
                return self._erro(f"Erro interno: {exc}", 500)

        self.send_error(404, "Rota não encontrada")


def main() -> int:
    parser = argparse.ArgumentParser(description="Interface web da carteira")
    parser.add_argument("--porta", type=int, default=8765)
    parser.add_argument("--sem-navegador", action="store_true")
    args = parser.parse_args()

    endereco = f"http://127.0.0.1:{args.porta}"
    servidor = ThreadingHTTPServer(("127.0.0.1", args.porta), Handler)

    ia_ok, ia_motivo = ai_insights.disponivel()
    print(f"\n  Portfolio Analyzer — {endereco}")
    print(f"  Análise por IA: {'disponível (' + ai_insights.MODELO + ')' if ia_ok else 'indisponível — ' + ia_motivo}")
    print(f"  Telegram: {'configurado' if notifier.configurado() else 'não configurado'}")
    print("  Ctrl+C para encerrar.\n")

    if not args.sem_navegador:
        threading.Timer(0.8, lambda: webbrowser.open(endereco)).start()

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n  Encerrando...")
        servidor.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())

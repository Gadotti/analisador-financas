#!/usr/bin/env python3
"""Análise da carteira — script isolado.

Este é o ÚNICO ponto do sistema que fala com a API da Anthropic e com o
Telegram. Roda sozinho (agendador de tarefas, terminal) ou é disparado pela
interface web como processo filho, sempre produzindo o mesmo resultado.

Uso:
    python scripts/analisar.py                  # análise completa no terminal
    python scripts/analisar.py --sem-ia         # somente cálculos, sem chamar a API
    python scripts/analisar.py --telegram       # envia o relatório ao Telegram
    python scripts/analisar.py --json           # resultado bruto em JSON no stdout
    python scripts/analisar.py --enviar-ultima  # reenvia a última análise salva
    python scripts/analisar.py --testar-telegram
    python scripts/analisar.py --testar-ia [--provedor kimi]

Em modo --json o stdout carrega APENAS o JSON; todo o progresso vai para o
stderr. É esse contrato que permite ao servidor web ler o resultado.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Permite rodar o script diretamente, sem instalar o pacote.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Saída em UTF-8 mesmo quando o console do Windows usa outra página de código.
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

from analise import ai_insights, notifier, report, runner  # noqa: E402


def montar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="analisar.py",
        description="Análise da carteira de investimentos",
    )
    parser.add_argument("--sem-ia", action="store_true", help="Pula a análise por IA")
    parser.add_argument("--telegram", action="store_true", help="Envia o relatório ao Telegram")
    parser.add_argument("--json", action="store_true", help="Imprime o resultado em JSON")
    parser.add_argument("--sem-cache", action="store_true", help="Ignora o cache de cotações")
    parser.add_argument("--nao-salvar", action="store_true", help="Não grava no histórico")
    parser.add_argument(
        "--enviar-ultima",
        action="store_true",
        help="Envia ao Telegram a última análise já salva, sem recalcular",
    )
    parser.add_argument(
        "--testar-telegram", action="store_true", help="Testa o bot do Telegram"
    )
    parser.add_argument(
        "--testar-ia",
        action="store_true",
        help="Testa a conexão com a API de IA (ping mínimo, gasta poucos tokens)",
    )
    parser.add_argument(
        "--provedor",
        help="Provedor a testar com --testar-ia (padrão: o ativo em IA_PROVEDOR)",
    )
    return parser


def main(argv: list[str] | None = None, *, out=None, err=None) -> int:
    """Executa o script. `out`/`err` são injetáveis para facilitar os testes."""
    out = out or sys.stdout
    err = err or sys.stderr

    args = montar_parser().parse_args(argv)

    # Em modo JSON o stdout é reservado ao JSON; o progresso vai para o stderr.
    canal_log = err if args.json else out

    def log(texto: str) -> None:
        print(texto, file=canal_log)

    def resposta_json(dados: dict) -> None:
        if args.json:
            print(json.dumps(dados, ensure_ascii=False), file=out)

    if args.testar_telegram:
        try:
            nome = notifier.testar()
        except Exception as exc:
            log(f"[ERRO] Telegram: {exc}")
            resposta_json({"erro": str(exc)})
            return 1
        log(f"[OK] Conectado ao bot '{nome}' — mensagem de teste enviada.")
        resposta_json({"ok": True, "bot": nome})
        return 0

    if args.testar_ia:
        try:
            resultado = ai_insights.testar_conexao(args.provedor)
        except Exception as exc:
            log(f"[ERRO] IA: {exc}")
            resposta_json({"erro": str(exc)})
            return 1
        log(
            f"[OK] Conectado a {resultado['provedor']} ({resultado['modelo']}) — "
            f"resposta: {resultado['resposta']!r}."
        )
        resposta_json(resultado)
        return 0

    if args.enviar_ultima:
        ultima = runner.ultima_analise()
        if not ultima:
            mensagem = "Rode uma análise antes de enviar ao Telegram."
            log(f"[ERRO] {mensagem}")
            resposta_json({"erro": mensagem})
            return 1
        try:
            notifier.enviar(
                report.telegram(
                    ultima["snapshot"], ultima.get("ia"), ultima.get("fundamentos")
                )
            )
        except Exception as exc:
            log(f"[ERRO] {exc}")
            resposta_json({"erro": str(exc)})
            return 1
        log("[OK] Última análise enviada ao Telegram.")
        resposta_json({"ok": True})
        return 0

    inicio = datetime.now()
    log("\n[1/3] Carregando carteira e cotações...")

    resultado = runner.executar(
        usar_ia=not args.sem_ia,
        usar_cache=not args.sem_cache,
        salvar=not args.nao_salvar,
    )
    snapshot, ia = resultado["snapshot"], resultado["ia"]
    fundamentos = resultado.get("fundamentos")

    log(
        f"      {snapshot['totais']['posicoes']} posições · "
        f"{len(snapshot['alertas'])} alertas"
    )

    if args.sem_ia:
        log("[2/3] Análise por IA desativada (--sem-ia).")
    elif ia:
        log(f"[2/3] Análise por IA concluída ({ia.get('_meta', {}).get('modelo', '?')}).")
    else:
        log(f"[2/3] Análise por IA indisponível: {resultado['ia_erro']}")

    if args.json:
        print(json.dumps(resultado, ensure_ascii=False), file=out)
    else:
        print(report.texto(snapshot, ia, fundamentos), file=out)

    codigo = 0
    if args.telegram:
        log("[3/3] Enviando ao Telegram...")
        try:
            notifier.enviar(report.telegram(snapshot, ia, fundamentos))
            log("      [OK] Enviado.")
        except Exception as exc:
            log(f"      [ERRO] {exc}")
            codigo = 1
    else:
        log("[3/3] Envio ao Telegram não solicitado (use --telegram).")

    log(f"Concluído em {(datetime.now() - inicio).total_seconds():.1f}s\n")
    return codigo


if __name__ == "__main__":
    sys.exit(main())

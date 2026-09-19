#!/usr/bin/env python3
"""Análise da carteira — script isolado.

Este é o ÚNICO ponto do sistema que fala com a API da Anthropic e com o
Telegram. Roda sozinho (agendador de tarefas, terminal) ou é disparado pela
interface web como processo filho, sempre produzindo o mesmo resultado.

Uso:
    python scripts/analisar.py                  # análise completa no terminal
    python scripts/analisar.py --sem-ia         # somente cálculos, sem chamar a API
    python scripts/analisar.py --telegram       # envia a mensagem do dia ao Telegram
    python scripts/analisar.py --telegram --completo   # envia o relatório inteiro
    python scripts/analisar.py --previa-telegram       # mostra a mensagem, sem enviar
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
import os
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

    # IA_ENV_FILE aponta para um .env isolado (testes). Sem redirecionar
    # load_dotenv() para ele também, o carregamento padrão ainda encontrava o
    # .env real do projeto subindo os diretórios a partir do cwd e vazava
    # IA_PROVEDOR e as demais variáveis do provedor ativo do usuário para o
    # ambiente do processo — config_ia usa o ambiente como retaguarda quando
    # uma chave falta no arquivo isolado.
    load_dotenv(os.environ.get("IA_ENV_FILE") or None)
except ImportError:
    pass

from analise import (  # noqa: E402
    ai_insights,
    estado_envio,
    mensagem,
    notifier,
    portfolio,
    relevancia,
    report,
    runner,
)


def mensagem_do_telegram(registro: dict, *, completo: bool) -> dict:
    """A mensagem a enviar: texto e se vale enviá-la.

    Por padrão é a mensagem curta, montada pela seleção de
    `analise.relevancia` sobre a configuração do cadastro e sobre o que já foi
    enviado antes (`analise.estado_envio`), para não repetir um achado
    inalterado. `--completo` devolve o relatório inteiro de sempre, que
    continua servindo ao envio sob demanda, fora da deduplicação — e esse
    nunca é descartado, porque foi pedido de propósito.
    """
    snapshot, ia = registro["snapshot"], registro.get("ia")
    fundamentos = registro.get("fundamentos")
    if completo:
        return {
            "texto": mensagem.telegram(snapshot, ia, fundamentos),
            "vale_enviar": True,
            "modo": "completo",
            "itens": [],
        }

    selecao = relevancia.selecionar(
        snapshot,
        ia,
        fundamentos,
        portfolio.load()["config"],
        macro_anterior=registro.get("macro_anterior"),
        estado_envio=estado_envio.ler(),
    )
    return {
        "texto": mensagem.telegram_resumo(selecao),
        "vale_enviar": selecao["vale_enviar"],
        "modo": selecao["modo"],
        "itens": selecao["itens"],
    }


def _registrar_envio(registro: dict, itens_enviados: list[dict], *, persistir: bool = True) -> None:
    """Poda o estado de deduplicação e registra o que acabou de sair.

    Só é chamada depois de `notifier.enviar` ter sucesso na mensagem curta —
    o relatório completo (`--completo`) não participa da deduplicação.

    Também atualiza `enviado_telegram` no `registro` e, quando `persistir` (o
    inverso de `--nao-salvar`), regrava os arquivos já persistidos — sem essa
    segunda gravação, o selo do que acabou de ser enviado só apareceria na
    Visão geral depois da próxima execução, porque `runner.executar` anota
    *antes* deste envio acontecer.
    """
    snapshot, ia = registro["snapshot"], registro.get("ia") or {}
    pool = {
        "alertas": snapshot["alertas"],
        "riscos_ia": ia.get("riscos") or [],
        "fatos_ia": ia.get("fatos") or [],
    }
    estado = estado_envio.podar(estado_envio.ler(), pool)
    chaves_por_bloco: dict[str, list[str]] = {}
    for item in itens_enviados:
        chave = item.get("chave_envio")
        if chave:
            chaves_por_bloco.setdefault(item["bloco"], []).append(chave)
    estado_envio.gravar(estado_envio.registrar_envio(estado, chaves_por_bloco))

    runner.reanotar_envio(registro)
    if persistir:
        runner.regravar_anotacao(registro)


def montar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="analisar.py",
        description="Análise da carteira de investimentos",
    )
    parser.add_argument("--sem-ia", action="store_true", help="Pula a análise por IA")
    parser.add_argument("--telegram", action="store_true", help="Envia a mensagem do dia ao Telegram")
    parser.add_argument(
        "--completo",
        action="store_true",
        help="Envia o relatório inteiro em vez da mensagem curta do dia",
    )
    parser.add_argument(
        "--previa-telegram",
        action="store_true",
        help="Mostra a mensagem que seria enviada hoje, sem enviar nada",
    )
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

    if args.enviar_ultima or args.previa_telegram:
        ultima = runner.ultima_analise()
        if not ultima:
            # Não chame esta variável de `mensagem`: o nome é o do módulo
            # importado, e sombreá-lo aqui quebraria o envio.
            motivo = "Rode uma análise antes de enviar ao Telegram."
            log(f"[ERRO] {motivo}")
            resposta_json({"erro": motivo})
            return 1

        aviso = mensagem_do_telegram(ultima, completo=args.completo)

        # A prévia é o que torna os limiares calibráveis: o usuário mexe num
        # número e vê o efeito com a carteira dele, sem gastar um envio.
        if args.previa_telegram:
            log(aviso["texto"])
            resposta_json({"ok": True, **aviso})
            return 0

        try:
            notifier.enviar(aviso["texto"])
        except Exception as exc:
            log(f"[ERRO] {exc}")
            resposta_json({"erro": str(exc)})
            return 1
        if aviso["modo"] != "completo":
            _registrar_envio(ultima, aviso["itens"])
        log("[OK] Última análise enviada ao Telegram.")
        resposta_json({"ok": True, "modo": aviso["modo"]})
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
        aviso = mensagem_do_telegram(resultado, completo=args.completo)
        if not aviso["vale_enviar"]:
            log("      [OK] Nada relevante hoje — envio dispensado (so_se_relevante).")
        else:
            try:
                notifier.enviar(aviso["texto"])
                log(f"      [OK] Enviado ({aviso['modo']}).")
            except Exception as exc:
                log(f"      [ERRO] {exc}")
                codigo = 1
            else:
                if aviso["modo"] != "completo":
                    _registrar_envio(resultado, aviso["itens"], persistir=not args.nao_salvar)
    else:
        log("[3/3] Envio ao Telegram não solicitado (use --telegram).")

    log(f"Concluído em {(datetime.now() - inicio).total_seconds():.1f}s\n")
    return codigo


if __name__ == "__main__":
    sys.exit(main())

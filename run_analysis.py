#!/usr/bin/env python3
"""Análise da carteira por linha de comando.

Uso:
    python run_analysis.py                  # análise completa, imprime no terminal
    python run_analysis.py --sem-ia         # apenas cálculos (não usa a API da Anthropic)
    python run_analysis.py --telegram       # envia o relatório ao Telegram
    python run_analysis.py --json           # imprime o resultado bruto em JSON
    python run_analysis.py --testar-telegram

Pensado também para o Agendador de Tarefas do Windows — veja agendar_tarefa.ps1.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

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

from core import notifier, report, runner  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Análise da carteira de investimentos")
    parser.add_argument("--sem-ia", action="store_true", help="Pula a análise por IA")
    parser.add_argument("--telegram", action="store_true", help="Envia o relatório ao Telegram")
    parser.add_argument("--json", action="store_true", help="Imprime o resultado em JSON")
    parser.add_argument("--sem-cache", action="store_true", help="Ignora o cache de cotações")
    parser.add_argument("--nao-salvar", action="store_true", help="Não grava no histórico")
    parser.add_argument("--testar-telegram", action="store_true", help="Testa o bot do Telegram")
    args = parser.parse_args()

    if args.testar_telegram:
        try:
            nome = notifier.testar()
        except Exception as exc:
            print(f"[ERRO] Telegram: {exc}")
            return 1
        print(f"[OK] Conectado ao bot '{nome}' — mensagem de teste enviada.")
        return 0

    inicio = datetime.now()
    if not args.json:
        print(f"\n[1/3] Carregando carteira e cotações...")

    resultado = runner.executar(
        usar_ia=not args.sem_ia,
        usar_cache=not args.sem_cache,
        salvar=not args.nao_salvar,
    )
    snapshot, ia = resultado["snapshot"], resultado["ia"]
    fundamentos = resultado.get("fundamentos")

    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return 0

    print(f"      {snapshot['totais']['posicoes']} posições · "
          f"{len(snapshot['alertas'])} alertas")

    if args.sem_ia:
        print("[2/3] Análise por IA desativada (--sem-ia).")
    elif ia:
        meta = ia.get("_meta", {})
        print(f"[2/3] Análise por IA concluída ({meta.get('modelo', '?')}).")
    else:
        print(f"[2/3] Análise por IA indisponível: {resultado['ia_erro']}")

    print(report.texto(snapshot, ia, fundamentos))

    if args.telegram:
        print("[3/3] Enviando ao Telegram...")
        try:
            notifier.enviar(report.telegram(snapshot, ia, fundamentos))
            print("      [OK] Enviado.")
        except Exception as exc:
            print(f"      [ERRO] {exc}")
            return 1
    else:
        print("[3/3] Envio ao Telegram não solicitado (use --telegram).")

    print(f"Concluído em {(datetime.now() - inicio).total_seconds():.1f}s\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

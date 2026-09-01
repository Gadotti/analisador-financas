"""Orquestra a análise completa e persiste o resultado.

Usado tanto pelo CLI (`run_analysis.py`, agendador de tarefas) quanto pelo
servidor da interface web — garantindo que ambos produzam o mesmo resultado.
"""

from __future__ import annotations

import json
from datetime import datetime

from . import ai_insights, analysis, fundamentals, portfolio
from .paths import HISTORY_DIR, LAST_ANALYSIS_FILE


def executar(*, usar_ia: bool = True, usar_cache: bool = True, salvar: bool = True) -> dict:
    """Roda a análise da carteira.

    A parte determinística sempre roda. A análise por IA é opcional e, se
    falhar, o resultado ainda é devolvido com o campo `ia_erro` preenchido.
    """
    carteira = portfolio.load()
    snapshot = analysis.consolidar(carteira, usar_cache=usar_cache)

    resultado = {
        "snapshot": snapshot,
        "ia": None,
        "fundamentos": None,
        "ia_erro": None,
        "ia_solicitada": usar_ia,
    }

    if usar_ia:
        if not snapshot["posicoes"]:
            resultado["ia_erro"] = "Carteira vazia — nada a analisar."
        else:
            try:
                resultado["ia"] = ai_insights.analisar(snapshot, carteira["config"])
            except ai_insights.IAIndisponivel as exc:
                resultado["ia_erro"] = str(exc)
            except Exception as exc:  # falha inesperada não derruba o relatório
                resultado["ia_erro"] = f"Falha inesperada na analise por IA: {exc}"

    # Métricas derivadas das fichas: aritmética local, não estimativa do modelo.
    resultado["fundamentos"] = fundamentals.consolidar(snapshot, resultado["ia"])

    if salvar:
        _persistir(resultado)

    return resultado


def _persistir(resultado: dict) -> None:
    registro = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        **resultado,
    }
    with open(LAST_ANALYSIS_FILE, "w", encoding="utf-8") as f:
        json.dump(registro, f, ensure_ascii=False, indent=2)

    arquivo = HISTORY_DIR / f"{resultado['snapshot']['data']}.json"
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(registro, f, ensure_ascii=False, indent=2)


def ultima_analise() -> dict | None:
    try:
        with open(LAST_ANALYSIS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def historico(limite: int = 60) -> list[dict]:
    """Série histórica do valor da carteira, da data mais antiga para a mais recente."""
    arquivos = sorted(HISTORY_DIR.glob("*.json"))[-limite:]
    serie = []
    for arquivo in arquivos:
        try:
            with open(arquivo, "r", encoding="utf-8") as f:
                dados = json.load(f)
            totais = dados["snapshot"]["totais"]
            serie.append({
                "data": dados["snapshot"]["data"],
                "valor_investido": totais["valor_investido"],
                "valor_atual": totais["valor_atual"],
                "resultado": totais["resultado"],
                "resultado_pct": totais["resultado_pct"],
                "saude": dados["snapshot"]["saude_carteira"],
            })
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    return serie

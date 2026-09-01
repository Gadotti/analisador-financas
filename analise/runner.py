"""Orquestra a análise completa e persiste o resultado.

Chamado pelo script isolado `scripts/analisar.py`, seja no terminal, pelo
agendador de tarefas ou disparado pela interface web — de modo que as três
origens produzam exatamente o mesmo resultado.
"""

from __future__ import annotations

import json
from datetime import datetime

from . import ai_insights, analysis, fundamentals, portfolio
from .paths import garantir_diretorios, history_dir, last_analysis_file


def executar(
    *,
    usar_ia: bool = True,
    usar_cache: bool = True,
    salvar: bool = True,
    analisar_com_ia=None,
) -> dict:
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
                analisador = analisar_com_ia or ai_insights.analisar
                resultado["ia"] = analisador(snapshot, carteira["config"])
            except ai_insights.IAIndisponivel as exc:
                resultado["ia_erro"] = str(exc)
            except Exception as exc:  # falha inesperada não derruba o relatório
                resultado["ia_erro"] = f"Falha inesperada na analise por IA: {exc}"

    # Métricas derivadas das fichas: aritmética local, não estimativa do modelo.
    resultado["fundamentos"] = fundamentals.consolidar(snapshot, resultado["ia"])

    if salvar:
        persistir(resultado)

    return resultado


def persistir(resultado: dict) -> dict:
    registro = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        **resultado,
    }
    garantir_diretorios()
    with open(last_analysis_file(), "w", encoding="utf-8") as f:
        json.dump(registro, f, ensure_ascii=False, indent=2)

    arquivo = history_dir() / f"{resultado['snapshot']['data']}.json"
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(registro, f, ensure_ascii=False, indent=2)

    return registro


def ultima_analise() -> dict | None:
    try:
        with open(last_analysis_file(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def historico(limite: int = 60) -> list[dict]:
    """Série histórica do valor da carteira, da data mais antiga para a mais recente."""
    arquivos = sorted(history_dir().glob("*.json"))[-limite:]
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

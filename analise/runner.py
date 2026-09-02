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
    Sem leitura nova, as fichas da última análise salva são herdadas — ver
    `_reaproveitar_ia`.
    """
    carteira = portfolio.load()
    snapshot = analysis.consolidar(carteira, usar_cache=usar_cache)

    resultado = {
        "snapshot": snapshot,
        "ia": None,
        "fundamentos": None,
        "ia_erro": None,
        "ia_solicitada": usar_ia,
        "ia_reaproveitada_de": None,
    }

    if usar_ia:
        resultado["ia"], resultado["ia_erro"] = _analisar_com_ia(
            snapshot, carteira["config"], analisar_com_ia
        )
    if resultado["ia"] is None:
        _reaproveitar_ia(resultado)

    # Métricas derivadas das fichas: aritmética local, não estimativa do modelo.
    resultado["fundamentos"] = fundamentals.consolidar(snapshot, resultado["ia"])

    if salvar:
        persistir(resultado)

    return resultado


def _analisar_com_ia(snapshot: dict, config: dict, analisador) -> tuple[dict | None, str | None]:
    """Chama a IA e devolve `(leitura, erro)` — a falha nunca derruba o relatório."""
    if not snapshot["posicoes"]:
        return None, "Carteira vazia — nada a analisar."
    try:
        return (analisador or ai_insights.analisar)(snapshot, config), None
    except ai_insights.IAIndisponivel as exc:
        return None, str(exc)
    except Exception as exc:  # falha inesperada não derruba o relatório
        return None, f"Falha inesperada na analise por IA: {exc}"


def _reaproveitar_ia(resultado: dict) -> None:
    """Herda a leitura da última análise salva quando esta execução não tem uma.

    Uma execução sem IA (`--sem-ia`, o botão "Atualizar cotações") ou uma
    tentativa que falhou grava por cima do registro do dia. Sem esta herança o
    arquivo ficaria sem fichas e a alocação por classificação, segmento e
    gestora — além da tela de análise — sumiria da interface, mesmo havendo uma
    leitura válida em disco.

    As fichas são herdadas cruas: `fundamentals` recalcula pesos e valores com o
    snapshot de agora. `ia_reaproveitada_de` carrega a data de origem para que
    interface e relatório não apresentem a leitura antiga como recém-feita.
    """
    ia = (ultima_analise() or {}).get("ia")
    if not ia or not ia.get("ativos"):
        return
    resultado["ia"] = ia
    resultado["ia_reaproveitada_de"] = (ia.get("_meta") or {}).get("gerado_em")


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

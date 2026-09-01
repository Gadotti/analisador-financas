"""Métricas agregadas da carteira a partir das fichas levantadas pela IA.

A IA fornece os indicadores de cada ativo (P/VP, dividend yield, segmento,
gestora). Este módulo cruza essas fichas com o peso real de cada posição e
calcula os números do conjunto — médias ponderadas, renda estimada e
concentrações. Toda a aritmética acontece aqui, não no modelo.

Ponderação: pelo valor atual de mercado da posição, não pelo valor investido.
Ativos sem o indicador ficam de fora daquela média específica, e a cobertura
resultante é informada para que o número possa ser lido com o devido peso.
"""

from __future__ import annotations

from . import portfolio

CLASSIFICACAO_ROTULO = {
    "tijolo": "Tijolo",
    "papel": "Papel",
    "hibrido": "Híbrido",
    "fof": "FoF",
    "acao": "Ação",
    "outro": "Outro",
}


def _media_ponderada(itens: list[tuple[float, float]]) -> float | None:
    """Média de (valor, peso), ignorando pesos nulos."""
    total_peso = sum(peso for _, peso in itens)
    if not total_peso:
        return None
    return sum(valor * peso for valor, peso in itens) / total_peso


def _agrupar(fichas: list[dict], campo: str) -> list[dict]:
    """Soma o valor das posições por categoria (segmento, gestora, classificação)."""
    grupos: dict[str, dict] = {}
    for f in fichas:
        chave = (f.get(campo) or "Não informado").strip() or "Não informado"
        grupo = grupos.setdefault(chave, {"nome": chave, "valor": 0.0, "ativos": []})
        grupo["valor"] += f["valor_atual"]
        grupo["ativos"].append(f["ticker"])

    total = sum(g["valor"] for g in grupos.values())
    saida = []
    for g in grupos.values():
        saida.append({
            "nome": g["nome"],
            "valor": round(g["valor"], 2),
            "peso_pct": round(g["valor"] / total * 100, 2) if total else 0.0,
            "ativos": g["ativos"],
            "quantidade": len(g["ativos"]),
        })
    return sorted(saida, key=lambda g: g["valor"], reverse=True)


def consolidar(snapshot: dict, ia: dict | None) -> dict | None:
    """Cruza as fichas da IA com as posições e devolve as métricas do conjunto.

    Retorna None quando não há ficha alguma para cruzar.
    """
    if not ia or not ia.get("ativos"):
        return None

    # Indexa as posições de renda variável pelo ticker.
    posicoes = {
        p["ticker"]: p
        for p in snapshot["posicoes"]
        if p["tipo"] in portfolio.TIPOS_VARIAVEL
    }

    fichas: list[dict] = []
    sem_posicao: list[str] = []

    for ativo in ia["ativos"]:
        ticker = (ativo.get("ticker") or "").upper().strip()
        posicao = posicoes.get(ticker)
        if not posicao:
            sem_posicao.append(ticker)
            continue
        fichas.append({
            **ativo,
            "ticker": ticker,
            "tipo": posicao["tipo"],
            "valor_atual": posicao["valor_atual"],
            "peso_pct": posicao["peso_pct"],
            "resultado_pct": posicao["resultado_pct"],
            "preco_atual": posicao["preco_atual"],
            "preco_medio": posicao["preco_medio"],
            "quantidade": posicao["quantidade"],
            "classificacao_rotulo": CLASSIFICACAO_ROTULO.get(
                ativo.get("classificacao"), "—"
            ),
        })

    if not fichas:
        return None

    valor_rv = sum(f["valor_atual"] for f in fichas)

    # ── Médias ponderadas pelo valor de mercado ──
    com_pvp = [(f["p_vp"], f["valor_atual"]) for f in fichas if f.get("p_vp")]
    com_dy = [(f["dy_12m_pct"], f["valor_atual"]) for f in fichas if f.get("dy_12m_pct")]

    p_vp_medio = _media_ponderada(com_pvp)
    dy_medio = _media_ponderada(com_dy)

    # ── Renda estimada (apenas ativos com DY informado) ──
    renda_anual = sum(
        f["valor_atual"] * f["dy_12m_pct"] / 100 for f in fichas if f.get("dy_12m_pct")
    )

    # ── Extremos de valuation ──
    ordenados_pvp = sorted(
        [f for f in fichas if f.get("p_vp")], key=lambda f: f["p_vp"]
    )
    ordenados_dy = sorted(
        [f for f in fichas if f.get("dy_12m_pct")],
        key=lambda f: f["dy_12m_pct"],
        reverse=True,
    )

    return {
        "fichas": fichas,
        "valor_renda_variavel": round(valor_rv, 2),
        "metricas": {
            "p_vp_medio": round(p_vp_medio, 3) if p_vp_medio else None,
            "p_vp_cobertura": f"{len(com_pvp)}/{len(fichas)}",
            "dy_medio_pct": round(dy_medio, 2) if dy_medio else None,
            "dy_cobertura": f"{len(com_dy)}/{len(fichas)}",
            "renda_anual_estimada": round(renda_anual, 2),
            "renda_mensal_estimada": round(renda_anual / 12, 2),
            "com_desconto": sum(1 for f in fichas if f.get("p_vp") and f["p_vp"] < 1),
            "com_agio": sum(1 for f in fichas if f.get("p_vp") and f["p_vp"] > 1),
            "maior_desconto": ordenados_pvp[0]["ticker"] if ordenados_pvp else None,
            "maior_agio": ordenados_pvp[-1]["ticker"] if ordenados_pvp else None,
            "maior_dy": ordenados_dy[0]["ticker"] if ordenados_dy else None,
            "menor_dy": ordenados_dy[-1]["ticker"] if ordenados_dy else None,
        },
        "por_classificacao": _agrupar(fichas, "classificacao_rotulo"),
        "por_segmento": _agrupar(fichas, "segmento"),
        "por_gestora": _agrupar(fichas, "gestora"),
        "sem_posicao": sem_posicao,
    }

"""Métricas agregadas da carteira a partir das fichas levantadas pela IA.

A IA fornece os indicadores de cada ativo (P/VP, dividend yield, segmento,
gestora). Este módulo cruza essas fichas com o peso real de cada posição e
calcula os números do conjunto — médias ponderadas, renda estimada e
concentrações. Toda a aritmética acontece aqui, não no modelo.

Ponderação: pelo valor atual de mercado da posição, não pelo valor investido —
a exceção é o yield on cost, cuja base é o custo e que por isso pondera pelo
valor investido. Ativos sem o indicador ficam de fora daquela média
específica, e a cobertura resultante é informada para que o número possa ser
lido com o devido peso.
"""

from __future__ import annotations

from . import gestoras, portfolio

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


def _yield_on_cost(ficha: dict) -> float | None:
    """Converte o DY de mercado para a base do preço que o investidor pagou.

    O DY levantado pela IA é `proventos_12m / preço_atual`; sobre o custo médio
    a mesma renda vira `proventos_12m / preço_médio`. Como o numerador é o
    mesmo, basta reescalar pela razão entre os preços — nenhuma consulta nova.

    Atenção à leitura: o preço médio se forma com os aportes ao longo do tempo,
    enquanto os proventos são de doze meses fixos. Quem comprou há pouco tem um
    YoC que projeta o ritmo atual sobre o próprio custo, não o que recebeu.
    """
    dy = ficha.get("dy_12m_pct")
    preco_atual = ficha.get("preco_atual")
    preco_medio = ficha.get("preco_medio")
    if not dy or not preco_atual or not preco_medio:
        return None
    return round(dy * preco_atual / preco_medio, 2)


def _tipo_dominante(itens: list[dict]) -> str:
    """Tipo de ativo com maior valor no grupo — define a cor da barra na interface."""
    por_tipo: dict[str, float] = {}
    for f in itens:
        por_tipo[f["tipo"]] = por_tipo.get(f["tipo"], 0.0) + f["valor_atual"]
    return max(por_tipo, key=lambda t: por_tipo[t])


def _agrupar(fichas: list[dict], campo: str, base: float) -> list[dict]:
    """Soma o valor das posições por categoria (segmento, gestora, classificação).

    O peso é sobre o total de renda variável (`snapshot.bases_concentracao`), o
    regime a que toda ficha pertence — não sobre a carteira inteira nem sobre o
    total das fichas. Diluir um segmento de FII no que está em CDB responderia
    a outra pergunta, e essa a alocação por classe já responde. O limite de
    concentração configurado é lido na mesma base: 50% aqui é metade da renda
    variável.
    """
    grupos: dict[str, list[dict]] = {}
    for f in fichas:
        chave = (f.get(campo) or "Não informado").strip() or "Não informado"
        grupos.setdefault(chave, []).append(f)

    saida = []
    for nome, itens in grupos.items():
        valor = sum(f["valor_atual"] for f in itens)
        saida.append({
            "nome": nome,
            "valor": round(valor, 2),
            "peso_pct": round(valor / base * 100, 2) if base else 0.0,
            "ativos": [f["ticker"] for f in itens],
            "quantidade": len(itens),
            "tipo": _tipo_dominante(itens),
        })
    return sorted(saida, key=lambda g: g["valor"], reverse=True)


def _nao_coberto(base_rv: float, valor_com_ficha: float) -> dict:
    """Parte da renda variável que nenhum recorte alcança — o que não tem ficha.

    Na base do regime é a posição de renda variável que a IA não leu (um ticker
    novo, uma leitura parcial); a renda fixa não entra na conta porque não é da
    base. Normalmente vem zerada, e aí a interface não desenha a faixa.
    """
    valor = max(0.0, base_rv - valor_com_ficha)
    return {
        "valor": round(valor, 2),
        "peso_pct": round(valor / base_rv * 100, 2) if base_rv else 0.0,
    }


def _unificar_gestoras(fichas: list[dict]) -> None:
    """Reescreve a gestora de cada ficha com o nome canônico do seu grupo.

    A IA nomeia a mesma casa de formas diferentes ("XP Asset Management (XP
    Vista)" e "XP Vista Asset Management"); sem isso o recorte por gestora
    quebraria a concentração real em duas linhas. Ver analise.gestoras.
    """
    canonico = gestoras.unificar_variantes(f.get("gestora") for f in fichas)
    for f in fichas:
        nome = f.get("gestora")
        if nome in canonico:
            f["gestora"] = canonico[nome]


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
        ficha = {
            **ativo,
            "ticker": ticker,
            "tipo": posicao["tipo"],
            "valor_atual": posicao["valor_atual"],
            "valor_investido": posicao["valor_investido"],
            "peso_pct": posicao["peso_pct"],
            "resultado_pct": posicao["resultado_pct"],
            "preco_atual": posicao["preco_atual"],
            "preco_medio": posicao["preco_medio"],
            "quantidade": posicao["quantidade"],
            "classificacao_rotulo": CLASSIFICACAO_ROTULO.get(
                ativo.get("classificacao"), "—"
            ),
        }
        ficha["yoc_12m_pct"] = _yield_on_cost(ficha)
        fichas.append(ficha)

    if not fichas:
        return None

    _unificar_gestoras(fichas)

    valor_rv = sum(f["valor_atual"] for f in fichas)
    total_carteira = snapshot["totais"]["valor_atual"]
    # Base dos recortes: o regime das fichas, não a carteira. Ver `_agrupar`.
    base_rv = snapshot["bases_concentracao"]["renda_variavel"]

    # ── Médias ponderadas pelo valor de mercado ──
    com_pvp = [(f["p_vp"], f["valor_atual"]) for f in fichas if f.get("p_vp")]
    com_dy = [(f["dy_12m_pct"], f["valor_atual"]) for f in fichas if f.get("dy_12m_pct")]

    # O YoC pondera pelo valor investido, e não pelo de mercado: a base do
    # indicador é o custo, então a média precisa usar a mesma régua.
    com_yoc = [(f["yoc_12m_pct"], f["valor_investido"]) for f in fichas if f.get("yoc_12m_pct")]

    p_vp_medio = _media_ponderada(com_pvp)
    dy_medio = _media_ponderada(com_dy)
    yoc_medio = _media_ponderada(com_yoc)

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
            "yoc_medio_pct": round(yoc_medio, 2) if yoc_medio else None,
            "yoc_cobertura": f"{len(com_yoc)}/{len(fichas)}",
            "renda_anual_estimada": round(renda_anual, 2),
            "renda_mensal_estimada": round(renda_anual / 12, 2),
            "com_desconto": sum(1 for f in fichas if f.get("p_vp") and f["p_vp"] < 1),
            "com_agio": sum(1 for f in fichas if f.get("p_vp") and f["p_vp"] > 1),
            "maior_desconto": ordenados_pvp[0]["ticker"] if ordenados_pvp else None,
            "maior_agio": ordenados_pvp[-1]["ticker"] if ordenados_pvp else None,
            "maior_dy": ordenados_dy[0]["ticker"] if ordenados_dy else None,
            "menor_dy": ordenados_dy[-1]["ticker"] if ordenados_dy else None,
        },
        "valor_total_carteira": round(total_carteira, 2),
        # Base declarada com os recortes: quem exibe o peso precisa dizer sobre o quê.
        "valor_base_recortes": round(base_rv, 2),
        "nao_coberto": _nao_coberto(base_rv, valor_rv),
        "por_classificacao": _agrupar(fichas, "classificacao_rotulo", base_rv),
        "por_segmento": _agrupar(fichas, "segmento", base_rv),
        "por_gestora": _agrupar(fichas, "gestora", base_rv),
        "sem_posicao": sem_posicao,
    }

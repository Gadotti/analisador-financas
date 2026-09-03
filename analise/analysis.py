"""Consolidação da carteira: posições marcadas a mercado, alocação e alertas.

Esta camada é 100% determinística (sem IA) e não exige chave de API.
A análise qualitativa por IA vive em `analise.ai_insights` e é opcional.
"""

from __future__ import annotations

from datetime import date, datetime

from . import fixed_income, market, portfolio

CLASSES = {"fii": "FIIs", "acao": "Ações", "cdb": "CDBs", "tesouro": "Tesouro Direto"}

# O FGC cobre depósito bancário; título público responde pelo Tesouro Nacional.
TIPOS_COM_FGC = ("cdb",)


# ─────────────────────────────────────────────
# Posições
# ─────────────────────────────────────────────

def _posicao_variavel(pos: dict, cot: dict) -> dict:
    qtd = float(pos["quantidade"])
    pm = float(pos["preco_medio"])
    investido = qtd * pm
    preco = cot.get("preco")

    if preco is None:
        return {
            "id": pos["id"],
            "tipo": pos["tipo"],
            "descricao": pos["ticker"],
            "ticker": pos["ticker"],
            "nome": cot.get("nome", pos["ticker"]),
            "quantidade": qtd,
            "preco_medio": pm,
            "preco_atual": None,
            "valor_investido": round(investido, 2),
            "valor_atual": round(investido, 2),
            "resultado": 0.0,
            "resultado_pct": 0.0,
            "variacao_dia_pct": None,
            "observacao": pos.get("observacao", ""),
            "erro_cotacao": cot.get("erro", "cotacao indisponivel"),
        }

    atual = qtd * preco
    resultado = atual - investido
    return {
        "id": pos["id"],
        "tipo": pos["tipo"],
        "descricao": pos["ticker"],
        "ticker": pos["ticker"],
        "nome": cot.get("nome", pos["ticker"]),
        "quantidade": qtd,
        "preco_medio": pm,
        "preco_atual": round(preco, 2),
        "valor_investido": round(investido, 2),
        "valor_atual": round(atual, 2),
        "resultado": round(resultado, 2),
        "resultado_pct": round(resultado / investido * 100, 2) if investido else 0.0,
        "variacao_dia_pct": (
            round(cot["variacao_dia_pct"], 2)
            if cot.get("variacao_dia_pct") is not None else None
        ),
        "resultado_dia": (
            round(atual - qtd * cot["fechamento_anterior"], 2)
            if cot.get("fechamento_anterior") else None
        ),
        "fonte_cotacao": cot.get("fonte"),
        "observacao": pos.get("observacao", ""),
        "erro_cotacao": None,
    }


def _indexador_do_titulo(pos: dict, macro: dict) -> dict:
    """Só consulta o índice que o título realmente usa — IPCA custa uma chamada."""
    if pos["indexador"] == "IPCA":
        aplicacao = date.fromisoformat(pos["data_aplicacao"])
        return {"ipca_fator": market.ipca_acumulado(aplicacao).get("fator")}
    if pos["indexador"] == "SELIC":
        return {"selic_anual_pct": macro["selic_meta_pct"]["valor"]}
    return {}


def _posicao_renda_fixa(pos: dict, hoje: date, macro: dict) -> dict:
    """Marca a mercado um CDB ou um título do Tesouro Direto.

    `valor_atual` e `resultado` medem só o que segue aplicado no papel: num
    título com cupom periódico os juros já sacados aparecem à parte, em
    `resultado_total`.
    """
    calc = fixed_income.valorizar(
        pos,
        hoje=hoje,
        cdi_anual_pct=macro["cdi_anual_pct"]["valor"],
        **_indexador_do_titulo(pos, macro),
    )

    calculada = {
        "id": pos["id"],
        "tipo": pos["tipo"],
        "descricao": portfolio.descricao(pos),
        "emissor": portfolio.emissor(pos),
        "indexador": pos["indexador"],
        "taxa": pos["taxa"],
        "rotulo_taxa": portfolio.rotulo_taxa(pos),
        "data_aplicacao": pos["data_aplicacao"],
        "data_vencimento": pos["data_vencimento"],
        "liquidez_diaria": pos.get("liquidez_diaria", False),
        "pagamento_juros": calc["pagamento_juros"],
        "valor_investido": calc["valor_inicial"],
        "valor_atual": calc["valor_bruto"],
        "valor_liquido": calc["valor_liquido"],
        "resultado": calc["rendimento_bruto"],
        "resultado_pct": calc["rentabilidade_bruta_pct"],
        "resultado_liquido": calc["rendimento_liquido"],
        "resultado_liquido_pct": calc["rentabilidade_liquida_pct"],
        "pagamentos_realizados": calc["pagamentos_realizados"],
        "proximo_pagamento": calc["proximo_pagamento"],
        "juros_recebidos_bruto": calc["juros_recebidos_bruto"],
        "juros_recebidos_liquido": calc["juros_recebidos_liquido"],
        "resultado_total": calc["rendimento_total_bruto"],
        "resultado_total_pct": calc["rentabilidade_total_bruta_pct"],
        "resultado_total_liquido": calc["rendimento_total_liquido"],
        "resultado_total_liquido_pct": calc["rentabilidade_total_liquida_pct"],
        "taxa_efetiva_aa_pct": calc["taxa_efetiva_aa_pct"],
        "ir_aliquota_pct": calc["ir_aliquota_pct"],
        "ir_valor": calc["ir_valor"],
        "custodia_valor": calc["custodia_valor"],
        "dias_para_vencer": calc["dias_para_vencer"],
        "vencido": calc["vencido"],
        "observacao": pos.get("observacao", ""),
        "aviso": calc["aviso"],
    }
    # O banco emissor continua num campo próprio: o teto do FGC só vale para o
    # CDB, e o Tesouro não tem banco algum por trás.
    if pos["tipo"] == "cdb":
        calculada["banco"] = pos["banco"]
    return calculada


# ─────────────────────────────────────────────
# Alertas determinísticos
# ─────────────────────────────────────────────

def _exposicao_por_emissor(posicoes: list[dict], tipos: tuple[str, ...]) -> dict[str, float]:
    """Soma o valor atual dos títulos ainda ativos por emissor."""
    por_emissor: dict[str, float] = {}
    for p in posicoes:
        if p["tipo"] in tipos and not p["vencido"]:
            por_emissor[p["emissor"]] = por_emissor.get(p["emissor"], 0.0) + p["valor_atual"]
    return por_emissor


def _cobertura_fgc(valor: float, limite_fgc: float, *, garantido: bool) -> dict:
    """Quanto o emissor consome do teto do FGC — nada, quando não é banco.

    O Tesouro Direto não é coberto pelo FGC: quem responde pelo papel é o
    próprio Tesouro Nacional, então não há teto a estourar.
    """
    if not garantido:
        return {"garantia": portfolio.EMISSOR_TESOURO, "fgc_limite": None,
                "fgc_uso_pct": None, "acima_do_fgc": False}
    return {
        "garantia": "FGC",
        "fgc_limite": limite_fgc,
        "fgc_uso_pct": round(valor / limite_fgc * 100, 1) if limite_fgc else 0.0,
        "acima_do_fgc": valor > limite_fgc,
    }


def _emissores_renda_fixa(posicoes: list[dict], total: float, limite_fgc: float) -> list[dict]:
    """Exposição por emissor de renda fixa, com o consumo do teto do FGC.

    É o recorte que falta em `fundamentals`, que só percorre fichas de renda
    variável: nenhum emissor de renda fixa aparece lá.
    """
    emissores = [
        {
            "nome": nome,
            "valor": round(valor, 2),
            "peso_pct": round(valor / total * 100, 2) if total else 0.0,
            **_cobertura_fgc(valor, limite_fgc, garantido=nome != portfolio.EMISSOR_TESOURO),
        }
        for nome, valor in _exposicao_por_emissor(posicoes, portfolio.TIPOS_RENDA_FIXA).items()
    ]
    return sorted(emissores, key=lambda e: e["valor"], reverse=True)


def _alerta(severidade: str, titulo: str, descricao: str, alvo: str = "") -> dict:
    return {
        "severidade": severidade,
        "titulo": titulo,
        "descricao": descricao,
        "alvo": alvo,
        "origem": "calculo",
    }


def _gerar_alertas(posicoes: list[dict], total: float, config: dict) -> list[dict]:
    alertas: list[dict] = []

    limite_venc = int(config["alerta_vencimento_dias"])
    limite_conc = float(config["alerta_concentracao_pct"])
    limite_prej = float(config["alerta_prejuizo_pct"])
    limite_fgc = float(config["limite_fgc"])

    # 1. Vencimentos de renda fixa
    for p in posicoes:
        if p["tipo"] not in portfolio.TIPOS_RENDA_FIXA:
            continue
        dias = p["dias_para_vencer"]
        if p["vencido"]:
            alertas.append(_alerta(
                "alerta",
                f"{p['descricao']} venceu",
                f"Venceu em {_br(p['data_vencimento'])}. Valor liquido estimado de "
                f"{_moeda(p['valor_liquido'])} disponivel para reinvestimento.",
                p["descricao"],
            ))
        elif dias <= limite_venc:
            alertas.append(_alerta(
                "atencao",
                f"{p['descricao']} vence em {dias} dias",
                f"Vencimento em {_br(p['data_vencimento'])}. Planeje o reinvestimento de "
                f"{_moeda(p['valor_liquido'])} liquidos.",
                p["descricao"],
            ))

    # 2. Exposição por banco vs. teto do FGC — o Tesouro não é coberto por ele
    for banco, valor in _exposicao_por_emissor(posicoes, TIPOS_COM_FGC).items():
        if valor > limite_fgc:
            alertas.append(_alerta(
                "alerta",
                f"Exposicao ao {banco} acima do teto do FGC",
                f"{_moeda(valor)} aplicados no {banco}, acima do limite de "
                f"{_moeda(limite_fgc)} garantido pelo FGC por CPF/instituicao.",
                banco,
            ))

    # 3. Concentração por ativo
    if total > 0:
        for p in posicoes:
            peso = p["valor_atual"] / total * 100
            if peso > limite_conc:
                alertas.append(_alerta(
                    "atencao",
                    f"Concentracao em {p['descricao']}: {peso:.1f}%",
                    f"A posicao representa {peso:.1f}% da carteira, acima do limite de "
                    f"{limite_conc:.0f}% configurado.",
                    p["descricao"],
                ))

    # 4. Prejuízo relevante em renda variável
    for p in posicoes:
        if p["tipo"] in portfolio.TIPOS_VARIAVEL and p["resultado_pct"] <= -limite_prej:
            alertas.append(_alerta(
                "atencao",
                f"{p['descricao']} acumula {p['resultado_pct']:.1f}%",
                f"Preco medio {_moeda(p['preco_medio'])} contra cotacao atual "
                f"{_moeda(p['preco_atual'])}. Resultado de {_moeda(p['resultado'])}.",
                p["descricao"],
            ))

    # 5. Falhas de cotação
    sem_cotacao = [p["descricao"] for p in posicoes if p.get("erro_cotacao")]
    if sem_cotacao:
        alertas.append(_alerta(
            "info",
            "Cotacao indisponivel",
            f"Nao foi possivel obter a cotacao de: {', '.join(sem_cotacao)}. "
            f"Estas posicoes entraram na carteira pelo preco medio.",
            ", ".join(sem_cotacao),
        ))

    ordem = {"alerta": 0, "atencao": 1, "info": 2}
    alertas.sort(key=lambda a: ordem.get(a["severidade"], 3))
    return alertas


def _saude(alertas: list[dict], resultado_pct: float) -> str:
    if any(a["severidade"] == "alerta" for a in alertas):
        return "alerta"
    qtd_atencao = sum(1 for a in alertas if a["severidade"] == "atencao")
    if qtd_atencao >= 3 or resultado_pct <= -10:
        return "atencao"
    if qtd_atencao == 0 and resultado_pct >= 5:
        return "otima"
    return "boa"


# ─────────────────────────────────────────────
# Snapshot completo
# ─────────────────────────────────────────────

def consolidar(carteira: dict | None = None, *, usar_cache: bool = True) -> dict:
    """Calcula o estado atual da carteira. Não usa IA."""
    carteira = carteira or portfolio.load()
    config = carteira["config"]
    hoje = date.today()

    macro = market.cenario_macro()

    tickers = portfolio.tickers(carteira)
    cots = market.cotacoes(tickers, usar_cache=usar_cache) if tickers else {}

    posicoes: list[dict] = []
    for pos in carteira["posicoes"]:
        if pos["tipo"] in portfolio.TIPOS_VARIAVEL:
            posicoes.append(_posicao_variavel(pos, cots.get(pos["ticker"], {})))
        else:
            posicoes.append(_posicao_renda_fixa(pos, hoje, macro))

    total_investido = sum(p["valor_investido"] for p in posicoes)
    total_atual = sum(p["valor_atual"] for p in posicoes)
    resultado = total_atual - total_investido
    resultado_pct = (resultado / total_investido * 100) if total_investido else 0.0
    resultado_dia = sum(p.get("resultado_dia") or 0 for p in posicoes)

    for p in posicoes:
        p["peso_pct"] = round(p["valor_atual"] / total_atual * 100, 2) if total_atual else 0.0

    # Alocação por classe
    classes = {}
    for chave, rotulo in CLASSES.items():
        itens = [p for p in posicoes if p["tipo"] == chave]
        if not itens:
            continue
        valor = sum(p["valor_atual"] for p in itens)
        investido = sum(p["valor_investido"] for p in itens)
        classes[chave] = {
            "rotulo": rotulo,
            "posicoes": len(itens),
            "valor_investido": round(investido, 2),
            "valor_atual": round(valor, 2),
            "resultado": round(valor - investido, 2),
            "resultado_pct": round((valor - investido) / investido * 100, 2) if investido else 0.0,
            "peso_pct": round(valor / total_atual * 100, 2) if total_atual else 0.0,
        }

    alertas = _gerar_alertas(posicoes, total_atual, config)

    variaveis = [p for p in posicoes if p["tipo"] in portfolio.TIPOS_VARIAVEL and not p.get("erro_cotacao")]
    destaques = sorted(variaveis, key=lambda p: p["resultado_pct"], reverse=True)

    return {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "data": hoje.isoformat(),
        "perfil": carteira.get("perfil", ""),
        "totais": {
            "valor_investido": round(total_investido, 2),
            "valor_atual": round(total_atual, 2),
            "resultado": round(resultado, 2),
            "resultado_pct": round(resultado_pct, 2),
            "resultado_dia": round(resultado_dia, 2),
            "posicoes": len(posicoes),
        },
        "classes": classes,
        # Uma régua só: todo consumidor lê daqui o limite que o usuário configurou.
        "limite_concentracao_pct": float(config["alerta_concentracao_pct"]),
        "emissores_renda_fixa": _emissores_renda_fixa(
            posicoes, total_atual, float(config["limite_fgc"])
        ),
        "posicoes": posicoes,
        "alertas": alertas,
        "saude_carteira": _saude(alertas, resultado_pct),
        "destaques": {
            "melhores": destaques[:3],
            "piores": destaques[-3:][::-1] if len(destaques) > 3 else [],
        },
        "macro": macro,
    }


# ─────────────────────────────────────────────
# Formatação
# ─────────────────────────────────────────────

def _moeda(valor) -> str:
    if valor is None:
        return "-"
    txt = f"{abs(valor):,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
    return f"{'-' if valor < 0 else ''}R$ {txt}"


def _br(iso: str) -> str:
    try:
        return date.fromisoformat(iso).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return iso or "-"


moeda = _moeda
data_br = _br

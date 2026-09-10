"""Como cada posição da carteira é marcada a valor de hoje.

Uma função por natureza de ativo, porque as fontes não têm nada em comum:

  - renda variável lê a cotação da B3 (`market`);
  - papel bancário (CDB, LCI, LCA) é carregado na curva pelo indexador
    contratado (`fixed_income`);
  - título público troca a curva pelo preço de revenda do último pregão
    (`tesouro_direto`), mantendo o valor de curva ao lado.

Todas devolvem o mesmo formato de dicionário, para que `analysis.consolidar`
some, pese e ordene sem saber de onde veio cada número.
"""

from __future__ import annotations

from datetime import date

from . import fixed_income, market, portfolio, tesouro_direto


def variavel(pos: dict, cot: dict) -> dict:
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


def dados_do_tesouro(titulos: list[dict], *, usar_cache: bool) -> dict:
    """Taxa travada na compra e cotação de hoje de cada título, por id.

    As duas consultas são feitas de uma vez para a carteira inteira: são duas
    requisições, não duas por posição.
    """
    compras = tesouro_direto.taxas_na_compra(titulos, usar_cache=usar_cache)
    do_dia = tesouro_direto.cotacoes(usar_cache=usar_cache)
    return {
        t["id"]: {
            "compra": compras.get(t["id"]),
            "cotacao": tesouro_direto.cotacao_de(do_dia, t),
        }
        for t in titulos
    }


def _resolver_taxa(pos: dict, tesouro: dict | None) -> tuple[dict | None, str]:
    """A posição com a taxa que vale no cálculo, e de onde ela saiu.

    Um título do Tesouro não pede taxa no cadastro: ela é buscada no pregão da
    compra. Se o usuário informar uma mesmo assim, a dele manda — é ela que
    está no extrato da corretora.
    """
    if pos.get("taxa") is not None:
        return {**pos, "taxa": float(pos["taxa"])}, "cadastro"
    compra = (tesouro or {}).get("compra")
    if compra:
        return {**pos, "taxa": compra["taxa_pct"]}, "tesouro_transparente"
    return None, "indisponivel"


def _renda_fixa_sem_taxa(pos: dict) -> dict:
    """Título que não pôde ser calculado: entra pelo valor aplicado.

    Mesmo tratamento da renda variável sem cotação — a posição não some da
    carteira, só não rende, e o alerta explica o motivo.
    """
    aplicado = round(float(pos["valor_inicial"]), 2)
    return {
        "id": pos["id"],
        "tipo": pos["tipo"],
        "descricao": portfolio.descricao(pos),
        "emissor": portfolio.emissor(pos),
        "indexador": pos["indexador"],
        "taxa": None,
        "taxa_origem": "indisponivel",
        "rotulo_taxa": "taxa nao localizada",
        "data_aplicacao": pos["data_aplicacao"],
        "data_vencimento": pos["data_vencimento"],
        "pagamento_juros": pos.get("pagamento_juros") or "vencimento",
        "isento_ir": fixed_income.regime(pos["tipo"])["isento_ir"],
        "valor_investido": aplicado,
        "valor_atual": aplicado,
        "valor_liquido": aplicado,
        "resultado": 0.0,
        "resultado_pct": 0.0,
        "resultado_total": 0.0,
        "resultado_total_pct": 0.0,
        "juros_recebidos_bruto": 0.0,
        "juros_recebidos_liquido": 0.0,
        "pagamentos_realizados": 0,
        "proximo_pagamento": None,
        "dias_para_vencer": (portfolio.data_iso(pos["data_vencimento"]) - date.today()).days,
        "vencido": False,
        "marcado_a_mercado": False,
        "observacao": pos.get("observacao", ""),
        "erro_cotacao": "taxa do titulo nao localizada no Tesouro Transparente",
        "aviso": "Taxa nao localizada - a posicao entrou pelo valor aplicado.",
    }


def _campos_calculados(pos: dict, titulo: dict, calc: dict, origem: str) -> dict:
    """Traduz o cálculo do título para as chaves que o snapshot publica."""
    return {
        "id": pos["id"],
        "tipo": pos["tipo"],
        "descricao": portfolio.descricao(pos),
        "emissor": portfolio.emissor(pos),
        "indexador": pos["indexador"],
        "taxa": titulo["taxa"],
        "taxa_origem": origem,
        "rotulo_taxa": portfolio.rotulo_taxa(titulo),
        "data_aplicacao": pos["data_aplicacao"],
        "data_vencimento": pos["data_vencimento"],
        "liquidez_diaria": pos.get("liquidez_diaria", False),
        "pagamento_juros": calc["pagamento_juros"],
        "valor_investido": calc["valor_inicial"],
        "valor_atual": calc["valor_bruto"],
        "valor_na_curva": calc["valor_na_curva"],
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
        "isento_ir": calc["isento_ir"],
        "dias_para_vencer": calc["dias_para_vencer"],
        "vencido": calc["vencido"],
        "observacao": pos.get("observacao", ""),
        "aviso": calc["aviso"],
    }


def _mercado_do_titulo(calc: dict, tesouro: dict | None) -> dict:
    """Troca o valor de curva pelo de mercado, quando há PU dos dois lados.

    A quantidade de títulos não é pedida no cadastro: ela sai do valor aplicado
    dividido pelo PU do dia da compra, que a mesma consulta já trouxe.
    """
    compra = (tesouro or {}).get("compra")
    cotacao = (tesouro or {}).get("cotacao")
    if not compra or not cotacao or not compra.get("pu_compra"):
        return calc
    quantidade = calc["valor_inicial"] / compra["pu_compra"]
    marcado = fixed_income.marcar_a_mercado(
        calc, quantidade=quantidade, pu_venda=cotacao["pu_venda"]
    )
    marcado["pu_compra"] = round(compra["pu_compra"], 2)
    marcado["cotacao_em"] = cotacao["data_base"]
    marcado["taxa_mercado_aa_pct"] = cotacao["taxa_venda_pct"]
    return marcado


def renda_fixa(pos: dict, hoje: date, macro: dict, tesouro: dict | None = None) -> dict:
    """Marca a mercado um papel bancário ou um título do Tesouro Direto.

    CDB, LCI e LCA são carregados na curva, que é o que o banco paga: não há
    mercado secundário para o investidor pessoa física. O título público tem
    preço de revenda publicado todo pregão, então `valor_atual` é esse preço, e
    o valor na curva segue ao lado, em `valor_na_curva`.

    `valor_atual` e `resultado` medem só o que segue aplicado no papel: num
    título com cupom periódico os juros já sacados aparecem à parte, em
    `resultado_total`.
    """
    titulo, origem = _resolver_taxa(pos, tesouro)
    if titulo is None:
        return _renda_fixa_sem_taxa(pos)

    calc = fixed_income.valorizar(
        titulo,
        hoje=hoje,
        cdi_anual_pct=macro["cdi_anual_pct"]["valor"],
        **_indexador_do_titulo(titulo, macro),
    )
    if pos["tipo"] == "tesouro":
        calc = _mercado_do_titulo(calc, tesouro)

    calculada = _campos_calculados(pos, titulo, calc, origem)
    calculada["marcado_a_mercado"] = "cotacao_em" in calc
    for extra in ("quantidade", "pu_compra", "pu_venda", "cotacao_em", "taxa_mercado_aa_pct"):
        if extra in calc:
            calculada[extra] = calc[extra]

    # O banco emissor continua num campo próprio: o teto do FGC só vale para o
    # papel bancário, e o Tesouro não tem banco algum por trás.
    if pos["tipo"] in portfolio.TIPOS_BANCARIOS:
        calculada["banco"] = pos["banco"]
    return calculada

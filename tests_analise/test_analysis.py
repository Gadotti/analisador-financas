"""Consolidação da carteira, alocação e alertas determinísticos."""

import pytest

from analise import analysis, fixed_income
from analise.portfolio import CONFIG_PADRAO
from conftest import RespostaFalsa, chart_yahoo

FII = {
    "id": "a1",
    "tipo": "fii",
    "ticker": "MXRF11",
    "quantidade": 1000.0,
    "preco_medio": 10.0,
    "observacao": "",
}

CDB = {
    "id": "b2",
    "tipo": "cdb",
    "banco": "Inter",
    "nome": "CDB Inter 110% do CDI",
    "valor_inicial": 10000.0,
    "indexador": "CDI",
    "taxa": 110.0,
    "data_aplicacao": "2025-01-02",
    "data_vencimento": "2099-01-04",
    "liquidez_diaria": False,
    "observacao": "",
}


TESOURO = {
    "id": "c3",
    "tipo": "tesouro",
    "nome": "Tesouro Selic 2029",
    "valor_inicial": 20000.0,
    "indexador": "SELIC",
    "taxa": 0.0949,
    "data_aplicacao": "2025-01-02",
    "data_vencimento": "2099-03-01",
    "pagamento_juros": "vencimento",
    "liquidez_diaria": False,
    "observacao": "",
}


def carteira_com(posicoes, **config):
    return {
        "versao": 2,
        "perfil": "teste",
        "posicoes": posicoes,
        "config": {**CONFIG_PADRAO, **config},
    }


# ─────────────────────────────────────────────
# consolidar
# ─────────────────────────────────────────────


def test_marca_a_mercado_renda_variavel_e_fixa(dados_temp, mercado_padrao):
    mercado_padrao.rotas["MXRF11.SA"] = chart_yahoo(11, 10, "Maxi Renda")

    snapshot = analysis.consolidar(carteira_com([FII, CDB]), usar_cache=False)

    fii = next(p for p in snapshot["posicoes"] if p["id"] == "a1")
    assert fii["valor_investido"] == 10000
    assert fii["valor_atual"] == 11000
    assert fii["resultado"] == 1000
    assert fii["resultado_pct"] == 10.0
    assert fii["resultado_dia"] == 1000

    cdb = next(p for p in snapshot["posicoes"] if p["id"] == "b2")
    assert cdb["tipo"] == "cdb"
    assert cdb["valor_atual"] > 10000
    assert cdb["rotulo_taxa"] == "110% do CDI"

    assert snapshot["totais"]["posicoes"] == 2
    assert snapshot["totais"]["valor_investido"] == 20000
    assert snapshot["perfil"] == "teste"


def test_distribui_peso_e_agrupa_por_classe(dados_temp, mercado_padrao):
    mercado_padrao.rotas["MXRF11.SA"] = chart_yahoo(11, 10)

    snapshot = analysis.consolidar(carteira_com([FII, CDB]), usar_cache=False)

    assert abs(sum(p["peso_pct"] for p in snapshot["posicoes"]) - 100) < 0.05
    assert list(snapshot["classes"]) == ["fii", "cdb"]
    assert snapshot["classes"]["fii"]["posicoes"] == 1
    assert snapshot["classes"]["fii"]["valor_atual"] == 11000


def test_cotacao_indisponivel_cai_no_preco_medio(dados_temp, mercado_padrao):
    mercado_padrao.rotas["MXRF11.SA"] = RuntimeError("indisponivel")
    mercado_padrao.rotas["brapi.dev"] = RuntimeError("indisponivel")

    snapshot = analysis.consolidar(carteira_com([FII]), usar_cache=False)

    fii = snapshot["posicoes"][0]
    assert fii["preco_atual"] is None
    assert fii["valor_atual"] == fii["valor_investido"]
    assert fii["resultado"] == 0
    assert fii["erro_cotacao"]
    assert any(a["titulo"] == "Cotacao indisponivel" for a in snapshot["alertas"])


def test_ipca_consultado_apenas_para_cdb_indexado(dados_temp, mercado_padrao):
    mercado_padrao.rotas["bcdata.sgs.433"] = RespostaFalsa([{"valor": "0,50"}])
    cdb_ipca = {**CDB, "indexador": "IPCA", "taxa": 6.0}

    snapshot = analysis.consolidar(carteira_com([cdb_ipca]), usar_cache=False)

    assert any("dataInicial" in (c["params"] or {}) for c in mercado_padrao.chamadas)
    assert snapshot["posicoes"][0]["valor_atual"] > 10000


def test_cdb_de_juros_mensais_separa_o_que_ja_foi_pago(dados_temp, mercado_padrao):
    """Os cupons sacados ficam fora de `valor_atual` e aparecem à parte."""
    mensal = {**CDB, "pagamento_juros": "mensal", "data_aplicacao": "2020-01-02"}

    snapshot = analysis.consolidar(carteira_com([mensal]), usar_cache=False)
    pos = snapshot["posicoes"][0]

    assert pos["pagamento_juros"] == "mensal"
    assert pos["pagamentos_realizados"] > 12
    assert pos["proximo_pagamento"] > snapshot["data"]
    assert pos["juros_recebidos_liquido"] > 0
    assert pos["valor_atual"] < pos["valor_investido"] * 1.1, "o principal segue intacto"
    assert pos["resultado_total"] > pos["resultado"]


def test_destaques_ordenados_do_melhor_para_o_pior(dados_temp, mercado_padrao):
    mercado_padrao.rotas["MXRF11.SA"] = chart_yahoo(11, 10)
    mercado_padrao.rotas["HGLG11.SA"] = chart_yahoo(8, 8)
    outro = {**FII, "id": "c3", "ticker": "HGLG11"}

    snapshot = analysis.consolidar(carteira_com([FII, outro]), usar_cache=False)

    assert snapshot["destaques"]["melhores"][0]["ticker"] == "MXRF11"
    assert snapshot["destaques"]["melhores"][1]["ticker"] == "HGLG11"
    assert snapshot["destaques"]["piores"] == [], "poucos ativos: sem lista de piores"


def test_snapshot_publica_a_tabela_de_ir(dados_temp, mercado_padrao):
    # A interface compara oferta isenta com tributada; a alíquota sai daqui,
    # e não de uma cópia no front-end.
    snapshot = analysis.consolidar(carteira_com([]), usar_cache=False)

    assert snapshot["ir_renda_fixa"] == fixed_income.faixas_ir()


def test_carteira_vazia_zera_os_totais(dados_temp, mercado_padrao):
    snapshot = analysis.consolidar(carteira_com([]), usar_cache=False)

    assert snapshot["totais"]["valor_atual"] == 0
    assert snapshot["totais"]["resultado_pct"] == 0
    assert snapshot["classes"] == {}
    assert snapshot["alertas"] == []
    assert snapshot["saude_carteira"] == "boa"


# ─────────────────────────────────────────────
# alertas
# ─────────────────────────────────────────────

CDB_BASE = {
    "tipo": "cdb",
    "descricao": "CDB Inter",
    "banco": "Inter",
    "emissor": "Inter",
    "valor_atual": 10000.0,
    "valor_liquido": 9800.0,
    "valor_investido": 10000.0,
    "data_vencimento": "2026-10-01",
    "dias_para_vencer": 30,
    "vencido": False,
}


def test_alerta_de_vencimento_proximo_e_vencido():
    vencido = {**CDB_BASE, "descricao": "CDB Velho", "vencido": True, "dias_para_vencer": -5}
    alertas = analysis._gerar_alertas([CDB_BASE, vencido], 20000, CONFIG_PADRAO)

    assert any(a["severidade"] == "atencao" and "vence em 30 dias" in a["titulo"] for a in alertas)
    assert any(a["severidade"] == "alerta" and "venceu" in a["titulo"] for a in alertas)


def test_exposicao_por_banco_soma_e_compara_com_o_fgc():
    posicoes = [
        {**CDB_BASE, "valor_atual": 200000.0, "dias_para_vencer": 999},
        {**CDB_BASE, "valor_atual": 100000.0, "dias_para_vencer": 999},
    ]
    alertas = analysis._gerar_alertas(posicoes, 300000, CONFIG_PADRAO)

    fgc = next(a for a in alertas if "teto do FGC" in a["titulo"])
    assert "R$ 300.000,00" in fgc["descricao"]


def test_teto_do_fgc_soma_cdb_e_letra_do_mesmo_banco():
    """O teto é por CPF/instituição, não por papel: CDB, LCI e LCA dividem um."""
    posicoes = [
        {**CDB_BASE, "valor_atual": 150000.0, "dias_para_vencer": 999},
        {**CDB_BASE, "tipo": "lci", "descricao": "LCI Inter", "valor_atual": 90000.0,
         "dias_para_vencer": 999},
        {**CDB_BASE, "tipo": "lca", "descricao": "LCA Inter", "valor_atual": 90000.0,
         "dias_para_vencer": 999},
    ]
    alertas = analysis._gerar_alertas(posicoes, 330000.0, CONFIG_PADRAO)

    fgc = next(a for a in alertas if "teto do FGC" in a["titulo"])
    assert "R$ 330.000,00" in fgc["descricao"]
    assert "Inter" in fgc["alvo"]


def test_emissores_de_renda_fixa_medem_o_consumo_do_fgc():
    posicoes = [
        {**CDB_BASE, "valor_atual": 200000.0, "dias_para_vencer": 999},
        {**CDB_BASE, "banco": "BTG", "emissor": "BTG", "valor_atual": 50000.0, "dias_para_vencer": 999},
    ]
    # A base é o total de renda fixa, não o da carteira: 250 mil dividem 100%.
    emissores = analysis._emissores_renda_fixa(posicoes, 250000.0, 250000.0)

    assert [e["nome"] for e in emissores] == ["Inter", "BTG"]
    assert emissores[0]["peso_pct"] == 80.0
    assert emissores[1]["peso_pct"] == 20.0
    assert emissores[0]["fgc_uso_pct"] == 80.0
    assert emissores[0]["acima_do_fgc"] is False


def test_emissor_acima_do_teto_do_fgc_e_sinalizado():
    posicoes = [{**CDB_BASE, "valor_atual": 300000.0, "dias_para_vencer": 999}]
    emissores = analysis._emissores_renda_fixa(posicoes, 300000.0, 250000.0)

    assert emissores[0]["acima_do_fgc"] is True
    assert emissores[0]["fgc_uso_pct"] == 120.0


def test_cdb_vencido_nao_conta_na_exposicao_do_banco():
    posicoes = [
        {**CDB_BASE, "valor_atual": 200000.0, "dias_para_vencer": 999},
        {**CDB_BASE, "valor_atual": 200000.0, "vencido": True, "dias_para_vencer": -1},
    ]
    alertas = analysis._gerar_alertas(posicoes, 400000, CONFIG_PADRAO)

    assert not any("teto do FGC" in a["titulo"] for a in alertas)


def test_alerta_de_concentracao():
    posicoes = [{"tipo": "fii", "descricao": "MXRF11", "valor_atual": 8000.0, "resultado_pct": 0.0}]
    alertas = analysis._gerar_alertas(posicoes, 10000, CONFIG_PADRAO)

    assert any("Concentracao em MXRF11: 80.0%" in a["titulo"] for a in alertas)


def test_alerta_de_prejuizo_relevante():
    posicoes = [
        {
            "tipo": "fii",
            "descricao": "MXRF11",
            "valor_atual": 100.0,
            "resultado_pct": -20.0,
            "resultado": -25.0,
            "preco_medio": 10.0,
            "preco_atual": 8.0,
        }
    ]
    alertas = analysis._gerar_alertas(posicoes, 100, {**CONFIG_PADRAO, "alerta_concentracao_pct": 200})

    assert any("acumula -20.0%" in a["titulo"] for a in alertas)


def test_alertas_ordenados_por_severidade():
    posicoes = [
        {"tipo": "fii", "descricao": "X", "valor_atual": 1.0, "resultado_pct": 0.0, "erro_cotacao": "x"},
        {**CDB_BASE, "descricao": "Venceu", "vencido": True, "dias_para_vencer": -1},
    ]
    alertas = analysis._gerar_alertas(posicoes, 2, CONFIG_PADRAO)

    ordem = {"alerta": 0, "atencao": 1, "info": 2}
    severidades = [a["severidade"] for a in alertas]
    assert "alerta" in severidades and "info" in severidades
    assert severidades == sorted(severidades, key=lambda s: ordem[s])


# ─────────────────────────────────────────────
# saúde
# ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "alertas,resultado_pct,esperado",
    [
        ([{"severidade": "alerta"}], 50, "alerta"),
        ([{"severidade": "atencao"}], 50, "boa"),
        ([{"severidade": "atencao"}] * 3, 50, "atencao"),
        ([], 6, "otima"),
        ([], 1, "boa"),
        ([], -12, "atencao"),
    ],
)
def test_saude_da_carteira(alertas, resultado_pct, esperado):
    assert analysis._saude(alertas, resultado_pct) == esperado


# ─────────────────────────────────────────────
# Tesouro Direto
# ─────────────────────────────────────────────


def test_titulo_do_tesouro_entra_como_classe_propria(dados_temp, mercado_padrao):
    snapshot = analysis.consolidar(carteira_com([CDB, TESOURO]), usar_cache=False)

    assert snapshot["classes"]["tesouro"]["rotulo"] == "Tesouro Direto"
    assert snapshot["classes"]["tesouro"]["posicoes"] == 1
    assert snapshot["classes"]["cdb"]["posicoes"] == 1
    assert snapshot["totais"]["posicoes"] == 2


def test_tesouro_selic_usa_a_meta_selic_do_cenario_macro(dados_temp, mercado_padrao):
    snapshot = analysis.consolidar(carteira_com([TESOURO]), usar_cache=False)
    titulo = snapshot["posicoes"][0]

    # mercado_padrao publica Selic meta de 15,00% a.a.; a taxa soma o ágio.
    assert titulo["taxa_efetiva_aa_pct"] == 15.0949
    assert titulo["rotulo_taxa"] == "SELIC + 0.0949% a.a."
    assert titulo["descricao"] == "Tesouro Selic 2029"
    assert titulo["emissor"] == "Tesouro Nacional"
    assert titulo["aviso"] is None
    assert titulo["custodia_valor"] > 0
    assert "banco" not in titulo


def test_tesouro_aparece_entre_os_emissores_sem_teto_do_fgc(dados_temp, mercado_padrao):
    snapshot = analysis.consolidar(carteira_com([CDB, TESOURO]), usar_cache=False)
    emissores = {e["nome"]: e for e in snapshot["emissores_renda_fixa"]}

    assert emissores["Tesouro Nacional"]["garantia"] == "Tesouro Nacional"
    assert emissores["Tesouro Nacional"]["fgc_limite"] is None
    assert emissores["Tesouro Nacional"]["acima_do_fgc"] is False
    assert emissores["Inter"]["garantia"] == "FGC"
    assert emissores["Inter"]["fgc_limite"] == CONFIG_PADRAO["limite_fgc"]


def test_bases_de_concentracao_separam_os_regimes(dados_temp, mercado_padrao):
    mercado_padrao.rotas["MXRF11.SA"] = chart_yahoo(11, 10, "Maxi Renda")

    snapshot = analysis.consolidar(carteira_com([FII, CDB, TESOURO]), usar_cache=False)
    bases = snapshot["bases_concentracao"]

    assert bases["carteira"] == snapshot["totais"]["valor_atual"]
    assert bases["renda_variavel"] == 11000.0
    assert round(bases["renda_variavel"] + bases["renda_fixa"], 2) == bases["carteira"]
    # Os emissores dividem a renda fixa entre si, e não a carteira inteira.
    assert round(sum(e["peso_pct"] for e in snapshot["emissores_renda_fixa"]), 1) == 100.0


def test_letra_de_credito_entra_nas_classes_e_no_recorte_por_emissor(
    dados_temp, mercado_padrao
):
    lci = {
        "id": "d4",
        "tipo": "lci",
        "banco": "Sofisa",
        "nome": "LCI Sofisa 95% do CDI",
        "valor_inicial": 5000.0,
        "indexador": "CDI",
        "taxa": 95.0,
        "data_aplicacao": "2025-01-02",
        "data_vencimento": "2099-01-04",
        "pagamento_juros": "vencimento",
        "liquidez_diaria": False,
        "observacao": "",
    }
    snapshot = analysis.consolidar(carteira_com([CDB, lci]), usar_cache=False)
    posicao = next(p for p in snapshot["posicoes"] if p["tipo"] == "lci")
    emissores = {e["nome"]: e for e in snapshot["emissores_renda_fixa"]}

    assert snapshot["classes"]["lci"]["rotulo"] == "LCIs"
    assert posicao["isento_ir"] is True
    assert posicao["ir_valor"] == 0.0
    assert posicao["banco"] == "Sofisa"
    assert posicao["emissor"] == "Sofisa"
    # A letra é renda fixa: entra na base do regime e no consumo do FGC.
    assert emissores["Sofisa"]["garantia"] == "FGC"
    assert snapshot["bases_concentracao"]["renda_fixa"] == round(
        snapshot["totais"]["valor_atual"], 2
    )


def test_concentracao_no_tesouro_nao_gera_alerta_de_fgc():
    """O teto do FGC é por banco: o Tesouro Nacional não o consome."""
    posicoes = [
        {
            "tipo": "tesouro",
            "descricao": "Tesouro Selic 2029",
            "emissor": "Tesouro Nacional",
            "valor_atual": 900000.0,
            "valor_liquido": 880000.0,
            "data_vencimento": "2029-03-01",
            "dias_para_vencer": 999,
            "vencido": False,
            "pagamento_juros": "vencimento",
        }
    ]
    alertas = analysis._gerar_alertas(posicoes, 900000.0, CONFIG_PADRAO)

    assert not any("teto do FGC" in a["titulo"] for a in alertas)


def test_vencimento_proximo_do_tesouro_tambem_alerta():
    titulo = {
        "tipo": "tesouro",
        "descricao": "Tesouro Prefixado 2026",
        "emissor": "Tesouro Nacional",
        "valor_atual": 10000.0,
        "valor_liquido": 9800.0,
        "data_vencimento": "2026-10-01",
        "dias_para_vencer": 20,
        "vencido": False,
        "pagamento_juros": "vencimento",
    }
    alertas = analysis._gerar_alertas([titulo], 10000.0, CONFIG_PADRAO)

    assert any("Tesouro Prefixado 2026 vence em 20 dias" in a["titulo"] for a in alertas)


# ─────────────────────────────────────────────
# Tesouro: taxa buscada e marcação a mercado
# ─────────────────────────────────────────────

# Sem `taxa`: ela sai do pregão da compra. Os PU do `mercado_padrao` para este
# papel são 15.745,70 na compra e 19.785,18 hoje.
TESOURO_SEM_TAXA = {
    "id": "c4",
    "tipo": "tesouro",
    "nome": "Tesouro Selic 2099",
    "valor_inicial": 10000.0,
    "indexador": "SELIC",
    "taxa": None,
    "data_aplicacao": "2025-01-02",
    "data_vencimento": "2099-03-01",
    "pagamento_juros": "vencimento",
    "liquidez_diaria": False,
    "observacao": "",
}


def test_taxa_do_tesouro_vem_do_pregao_da_compra(dados_temp, mercado_padrao):
    snapshot = analysis.consolidar(carteira_com([TESOURO_SEM_TAXA]), usar_cache=False)
    titulo = snapshot["posicoes"][0]

    assert titulo["taxa"] == 0.13
    assert titulo["taxa_origem"] == "tesouro_transparente"
    assert titulo["rotulo_taxa"] == "SELIC + 0.13% a.a."


def test_valor_atual_do_tesouro_e_o_preco_de_revenda(dados_temp, mercado_padrao):
    snapshot = analysis.consolidar(carteira_com([TESOURO_SEM_TAXA]), usar_cache=False)
    titulo = snapshot["posicoes"][0]

    # 10.000 / 15.745,70 = 0,635094 titulos, revendidos a 19.785,18 cada.
    assert titulo["quantidade"] == pytest.approx(10000 / 15745.70, rel=1e-6)
    assert titulo["valor_atual"] == pytest.approx(
        (10000 / 15745.70) * 19785.18, abs=0.01
    )
    assert titulo["marcado_a_mercado"] is True
    assert titulo["cotacao_em"] == "2026-09-03"
    assert titulo["pu_compra"] == 15745.70
    assert titulo["pu_venda"] == 19785.18


def test_valor_na_curva_segue_ao_lado_do_de_mercado(dados_temp, mercado_padrao):
    snapshot = analysis.consolidar(carteira_com([TESOURO_SEM_TAXA]), usar_cache=False)
    titulo = snapshot["posicoes"][0]

    assert titulo["valor_na_curva"] > 10000, "a curva rende desde a aplicacao"
    assert titulo["valor_na_curva"] != titulo["valor_atual"]
    assert titulo["resultado"] == round(titulo["valor_atual"] - 10000, 2)


def test_totais_da_carteira_usam_o_valor_de_mercado(dados_temp, mercado_padrao):
    snapshot = analysis.consolidar(carteira_com([TESOURO_SEM_TAXA]), usar_cache=False)

    assert snapshot["totais"]["valor_atual"] == snapshot["posicoes"][0]["valor_atual"]
    assert snapshot["classes"]["tesouro"]["valor_atual"] == snapshot["totais"]["valor_atual"]


def test_taxa_informada_no_cadastro_prevalece_sobre_a_buscada(dados_temp, mercado_padrao):
    """Quem tem a taxa no extrato da corretora manda nela."""
    snapshot = analysis.consolidar(
        carteira_com([{**TESOURO_SEM_TAXA, "taxa": 0.25}]), usar_cache=False
    )
    titulo = snapshot["posicoes"][0]

    assert titulo["taxa"] == 0.25
    assert titulo["taxa_origem"] == "cadastro"


def test_ir_do_tesouro_incide_sobre_o_ganho_de_mercado(dados_temp, mercado_padrao):
    snapshot = analysis.consolidar(carteira_com([TESOURO_SEM_TAXA]), usar_cache=False)
    titulo = snapshot["posicoes"][0]

    # O IR sai da tabela regressiva pelo prazo decorrido, e incide sobre o
    # ganho de MERCADO — nao sobre o da curva, que e outro numero.
    aliquota = titulo["ir_aliquota_pct"] / 100
    assert aliquota in (0.225, 0.20, 0.175, 0.15)
    assert titulo["ir_valor"] == pytest.approx(
        (titulo["valor_atual"] - 10000) * aliquota, abs=0.01
    )
    assert titulo["ir_valor"] != pytest.approx(
        (titulo["valor_na_curva"] - 10000) * aliquota, abs=0.01
    )
    assert titulo["valor_liquido"] == pytest.approx(
        titulo["valor_atual"] - titulo["ir_valor"] - titulo["custodia_valor"], abs=0.01
    )


def test_cdb_continua_na_curva_e_sem_marcacao(dados_temp, mercado_padrao):
    """Não há preço de revenda de CDB para pessoa física — a curva é o valor."""
    snapshot = analysis.consolidar(carteira_com([CDB]), usar_cache=False)
    cdb = snapshot["posicoes"][0]

    assert cdb["marcado_a_mercado"] is False
    assert cdb["valor_atual"] == cdb["valor_na_curva"]
    assert cdb["taxa_origem"] == "cadastro"


def test_titulo_sem_taxa_localizavel_entra_pelo_valor_aplicado(dados_temp, mercado_padrao):
    """Sem taxa no cadastro nem no arquivo, a posição não some nem inventa rendimento."""
    orfao = {**TESOURO_SEM_TAXA, "data_aplicacao": "2004-01-02", "indexador": "PRE"}
    snapshot = analysis.consolidar(carteira_com([orfao]), usar_cache=False)
    titulo = snapshot["posicoes"][0]

    assert titulo["valor_atual"] == 10000.0
    assert titulo["resultado"] == 0.0
    assert titulo["taxa_origem"] == "indisponivel"
    assert titulo["erro_cotacao"]
    assert any("Cotacao indisponivel" in a["titulo"] for a in snapshot["alertas"])

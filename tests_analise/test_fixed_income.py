"""Marcação a mercado de CDBs: calendário, IR e capitalização."""

from datetime import date

import pytest

from analise.fixed_income import (
    _pascoa,
    aliquota_ir,
    datas_pagamento,
    dias_uteis,
    feriados_nacionais,
    proximo_dia_util,
    somar_meses,
    valorizar,
)

CDB_CDI = {
    "tipo": "cdb",
    "banco": "Inter",
    "valor_inicial": 10000.0,
    "indexador": "CDI",
    "taxa": 110.0,
    "data_aplicacao": "2025-01-02",
    "data_vencimento": "2027-01-04",
}


@pytest.mark.parametrize(
    "ano,esperado",
    [(2024, date(2024, 3, 31)), (2025, date(2025, 4, 20)), (2026, date(2026, 4, 5))],
)
def test_pascoa(ano, esperado):
    assert _pascoa(ano) == esperado


def test_feriados_fixos_e_moveis():
    feriados = feriados_nacionais(2026)
    assert date(2026, 1, 1) in feriados, "Confraternização"
    assert date(2026, 12, 25) in feriados, "Natal"
    assert date(2026, 2, 16) in feriados, "Carnaval segunda"
    assert date(2026, 2, 17) in feriados, "Carnaval terça"
    assert date(2026, 4, 3) in feriados, "Sexta-feira Santa"
    assert date(2026, 6, 4) in feriados, "Corpus Christi"
    assert len(feriados) == 13


def test_dias_uteis_exclui_fim_de_semana_e_feriado():
    # 05/01 (seg) a 09/01 (sex): 4 dias úteis, excluindo o dia inicial.
    assert dias_uteis(date(2026, 1, 5), date(2026, 1, 9)) == 4
    # Natal de 2026 cai numa sexta.
    assert dias_uteis(date(2026, 12, 21), date(2026, 12, 25)) == 3


def test_dias_uteis_periodo_invertido_ou_nulo():
    assert dias_uteis(date(2026, 1, 10), date(2026, 1, 10)) == 0
    assert dias_uteis(date(2026, 1, 10), date(2026, 1, 1)) == 0


def test_dias_uteis_atravessa_o_ano():
    # 26, 29, 30, 31 de dezembro + 2 e 5 de janeiro
    assert dias_uteis(date(2025, 12, 24), date(2026, 1, 5)) == 6


@pytest.mark.parametrize(
    "dias,aliquota",
    [(0, 0.225), (180, 0.225), (181, 0.20), (360, 0.20), (361, 0.175), (720, 0.175), (721, 0.15)],
)
def test_tabela_regressiva_de_ir(dias, aliquota):
    assert aliquota_ir(dias) == aliquota


def test_cdi_capitaliza_em_dias_uteis_e_desconta_ir():
    calc = valorizar(CDB_CDI, hoje=date(2026, 1, 2), cdi_anual_pct=15.0)

    assert calc["taxa_efetiva_aa_pct"] == 16.5, "110% de 15% a.a."
    assert calc["valor_bruto"] > 10000
    assert calc["dias_corridos"] == 365
    assert calc["ir_aliquota_pct"] == 17.5, "acima de 360 dias corridos"
    assert calc["valor_liquido"] < calc["valor_bruto"]
    assert calc["rendimento_liquido"] == round(calc["valor_liquido"] - 10000, 2)
    assert calc["vencido"] is False
    assert calc["aviso"] is None


def test_prefixado_ignora_o_cdi():
    pre = {**CDB_CDI, "indexador": "PRE", "taxa": 12.0}
    a = valorizar(pre, hoje=date(2026, 1, 2), cdi_anual_pct=15.0)
    b = valorizar(pre, hoje=date(2026, 1, 2), cdi_anual_pct=5.0)

    assert a["valor_bruto"] == b["valor_bruto"]
    assert a["taxa_efetiva_aa_pct"] == 12.0


def test_ipca_usa_o_fator_quando_disponivel():
    ipca = {**CDB_CDI, "indexador": "IPCA", "taxa": 6.0}
    com = valorizar(ipca, hoje=date(2026, 1, 2), cdi_anual_pct=15.0, ipca_fator=1.05)
    sem = valorizar(ipca, hoje=date(2026, 1, 2), cdi_anual_pct=15.0)

    assert com["valor_bruto"] > sem["valor_bruto"]
    assert com["aviso"] is None
    assert "IPCA indisponivel" in sem["aviso"]


def test_juro_real_do_ipca_capitaliza_em_dias_uteis():
    """O spread real segue a base 252, como o CDI e o prefixado."""
    ipca = {**CDB_CDI, "indexador": "IPCA", "taxa": 6.0}
    calc = valorizar(ipca, hoje=date(2026, 1, 2), cdi_anual_pct=15.0, ipca_fator=1.10)

    esperado = 10000.0 * 1.10 * 1.06 ** (calc["dias_uteis"] / 252)

    assert calc["valor_bruto"] == round(esperado, 2)


def test_rendimento_congela_apos_o_vencimento():
    no_vencimento = valorizar(CDB_CDI, hoje=date(2027, 1, 4), cdi_anual_pct=15.0)
    bem_depois = valorizar(CDB_CDI, hoje=date(2028, 1, 4), cdi_anual_pct=15.0)

    assert no_vencimento["valor_bruto"] == bem_depois["valor_bruto"]
    assert bem_depois["vencido"] is True
    assert bem_depois["dias_para_vencer"] == -365


def test_vencido_exatamente_no_dia():
    calc = valorizar(CDB_CDI, hoje=date(2027, 1, 4), cdi_anual_pct=15.0)
    assert calc["vencido"] is True
    assert calc["dias_para_vencer"] == 0


def test_sem_rendimento_nao_cobra_ir():
    calc = valorizar(CDB_CDI, hoje=date(2025, 1, 2), cdi_anual_pct=15.0)

    assert calc["dias_uteis"] == 0
    assert calc["valor_bruto"] == 10000
    assert calc["ir_valor"] == 0
    assert calc["rentabilidade_liquida_pct"] == 0


# ─────────────────────────────────────────────
# Juros mensais
# ─────────────────────────────────────────────

CDB_MENSAL = {**CDB_CDI, "pagamento_juros": "mensal"}


def test_pagamento_no_vencimento_e_o_padrao():
    """Uma posição sem o campo se comporta como sempre se comportou."""
    calc = valorizar(CDB_CDI, hoje=date(2026, 1, 2), cdi_anual_pct=15.0)

    assert calc["pagamento_juros"] == "vencimento"
    assert calc["pagamentos_realizados"] == 0
    assert calc["juros_recebidos_bruto"] == 0
    assert calc["proximo_pagamento"] is None
    assert calc["rendimento_total_bruto"] == calc["rendimento_bruto"]
    assert calc["rendimento_total_liquido"] == calc["rendimento_liquido"]


@pytest.mark.parametrize(
    "dia,esperado",
    [
        (date(2026, 1, 5), date(2026, 1, 5)),   # segunda comum
        (date(2026, 1, 3), date(2026, 1, 5)),   # sábado
        (date(2026, 1, 1), date(2026, 1, 2)),   # feriado
        (date(2025, 12, 25), date(2025, 12, 26)),
    ],
)
def test_proximo_dia_util(dia, esperado):
    assert proximo_dia_util(dia) == esperado


@pytest.mark.parametrize(
    "inicio,meses,esperado",
    [
        (date(2025, 1, 2), 1, date(2025, 2, 2)),
        (date(2025, 1, 31), 1, date(2025, 2, 28)),   # fevereiro é curto
        (date(2025, 1, 31), 2, date(2025, 3, 31)),   # e o dia original volta
        (date(2025, 12, 15), 1, date(2026, 1, 15)),  # vira o ano
        (date(2025, 12, 31), 12, date(2026, 12, 31)),
    ],
)
def test_somar_meses(inicio, meses, esperado):
    assert somar_meses(inicio, meses) == esperado


def test_datas_de_pagamento_caem_em_dia_util():
    datas = datas_pagamento(date(2025, 1, 2), date(2027, 1, 4), date(2025, 6, 30))

    assert datas[0] == date(2025, 2, 3), "02/02 é domingo"
    assert datas[1] == date(2025, 3, 5), "02/03 é domingo e 03-04/03 é Carnaval"
    assert datas[-1] == date(2025, 6, 2), "nenhum aniversário depois de 30/06"
    assert len(datas) == 5


def test_juros_mensais_nao_capitalizam():
    """O principal fica intacto e cada mês rende sobre ele, sem juro sobre juro."""
    mensal = valorizar(CDB_MENSAL, hoje=date(2026, 1, 2), cdi_anual_pct=15.0)
    acumulado = valorizar(CDB_CDI, hoje=date(2026, 1, 2), cdi_anual_pct=15.0)

    assert mensal["pagamentos_realizados"] == 12
    assert mensal["valor_bruto"] == 10000, "o 12º cupom foi pago hoje"
    assert mensal["juros_recebidos_bruto"] > 0
    assert mensal["rendimento_total_bruto"] < acumulado["rendimento_bruto"]


def test_valor_aplicado_soma_o_rendimento_do_mes_em_curso():
    """Entre um cupom e outro, o título carrega só o rendimento do período."""
    calc = valorizar(CDB_MENSAL, hoje=date(2026, 1, 20), cdi_anual_pct=15.0)

    assert calc["pagamentos_realizados"] == 12
    assert 10000 < calc["valor_bruto"] < 10100
    assert calc["rendimento_bruto"] == round(calc["valor_bruto"] - 10000, 2)
    assert calc["proximo_pagamento"] == "2026-02-02"


def test_ir_de_cada_cupom_usa_o_prazo_ate_ele():
    """Os primeiros cupons pagam 22,5%; a alíquota média cai com o tempo."""
    calc = valorizar(CDB_MENSAL, hoje=date(2026, 1, 2), cdi_anual_pct=15.0)
    media = calc["juros_recebidos_ir"] / calc["juros_recebidos_bruto"]

    assert 0.175 < media < 0.225
    assert calc["juros_recebidos_liquido"] == round(
        calc["juros_recebidos_bruto"] - calc["juros_recebidos_ir"], 2
    )


def test_antes_do_primeiro_aniversario_nada_muda():
    mensal = valorizar(CDB_MENSAL, hoje=date(2025, 1, 20), cdi_anual_pct=15.0)
    acumulado = valorizar(CDB_CDI, hoje=date(2025, 1, 20), cdi_anual_pct=15.0)

    assert mensal["pagamentos_realizados"] == 0
    assert mensal["juros_recebidos_bruto"] == 0
    assert mensal["valor_bruto"] == acumulado["valor_bruto"]
    assert mensal["proximo_pagamento"] == "2025-02-03"


def test_apos_o_vencimento_nao_ha_proximo_pagamento():
    calc = valorizar(CDB_MENSAL, hoje=date(2028, 1, 4), cdi_anual_pct=15.0)

    assert calc["vencido"] is True
    assert calc["proximo_pagamento"] is None
    assert calc["pagamentos_realizados"] == 24


def test_ipca_reparte_a_correcao_entre_os_cupons():
    ipca = {**CDB_MENSAL, "indexador": "IPCA", "taxa": 6.0}
    com = valorizar(ipca, hoje=date(2026, 1, 2), cdi_anual_pct=15.0, ipca_fator=1.10)
    sem = valorizar(ipca, hoje=date(2026, 1, 2), cdi_anual_pct=15.0)

    assert com["juros_recebidos_bruto"] > sem["juros_recebidos_bruto"]
    assert "IPCA indisponivel" in sem["aviso"]

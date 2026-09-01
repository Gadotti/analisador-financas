"""Marcação a mercado de CDBs: calendário, IR e capitalização."""

from datetime import date

import pytest

from analise.fixed_income import (
    _pascoa,
    aliquota_ir,
    dias_uteis,
    feriados_nacionais,
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

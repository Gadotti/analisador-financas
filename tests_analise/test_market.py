"""Cotações, indicadores do Banco Central e cache em disco."""

from datetime import date

from analise import market
from conftest import RespostaFalsa, chart_yahoo


def test_cotacao_do_yahoo_calcula_variacao(dados_temp, rede):
    rede.rotas["MXRF11.SA"] = chart_yahoo(11, 10, "Maxi Renda")

    cot = market.cotacao("mxrf11", usar_cache=False)

    assert cot["ticker"] == "MXRF11"
    assert cot["preco"] == 11
    assert cot["fechamento_anterior"] == 10
    assert cot["variacao_dia_pct"] == 10
    assert cot["fonte"] == "yahoo"
    assert cot["do_cache"] is False


def test_cai_para_brapi_quando_yahoo_falha(dados_temp, rede):
    rede.rotas["query1.finance.yahoo.com"] = RuntimeError("timeout")
    rede.rotas["brapi.dev"] = RespostaFalsa(
        {
            "results": [
                {
                    "regularMarketPrice": 20,
                    "regularMarketPreviousClose": 19,
                    "regularMarketChangePercent": 5.26,
                    "shortName": "HGLG",
                }
            ]
        }
    )

    cot = market.cotacao("HGLG11", usar_cache=False)

    assert cot["fonte"] == "brapi"
    assert cot["preco"] == 20


def test_envia_token_da_brapi_quando_configurado(dados_temp, rede, monkeypatch):
    monkeypatch.setenv("BRAPI_TOKEN", "tok-123")
    rede.rotas["query1.finance.yahoo.com"] = RespostaFalsa({"chart": {"result": []}})
    rede.rotas["brapi.dev"] = RespostaFalsa({"results": [{"regularMarketPrice": 1}]})

    market.cotacao("XPTO11", usar_cache=False)

    chamada_brapi = next(c for c in rede.chamadas if "brapi.dev" in c["url"])
    assert chamada_brapi["params"]["token"] == "tok-123"


def test_erro_estruturado_quando_todas_as_fontes_falham(dados_temp, rede):
    rede.rotas["query1.finance.yahoo.com"] = RespostaFalsa({}, status=429)
    rede.rotas["brapi.dev"] = RespostaFalsa({"results": []})

    cot = market.cotacao("XXXX11", usar_cache=False)

    assert cot["preco"] is None
    assert "_yahoo" in cot["erro"]
    assert "_brapi: sem dados" in cot["erro"]


def test_cache_evita_nova_consulta(dados_temp, rede):
    rede.rotas["MXRF11.SA"] = chart_yahoo(11, 10)

    market.cotacao("MXRF11")
    do_cache = market.cotacao("MXRF11")

    assert do_cache["do_cache"] is True
    assert do_cache["preco"] == 11
    assert len(rede.chamadas) == 1


def test_sem_cache_consulta_de_novo(dados_temp, rede):
    rede.rotas["MXRF11.SA"] = chart_yahoo(11, 10)

    market.cotacao("MXRF11")
    market.cotacao("MXRF11", usar_cache=False)

    assert len(rede.chamadas) == 2


def test_cotacoes_indexa_por_ticker(dados_temp, rede):
    rede.rotas["query1.finance.yahoo.com"] = chart_yahoo(11, 10)

    cots = market.cotacoes(["MXRF11", "HGLG11"], usar_cache=False)

    assert list(cots) == ["MXRF11", "HGLG11"]


def test_cdi_converte_virgula_decimal(dados_temp, rede):
    rede.rotas["bcdata.sgs.4389"] = RespostaFalsa([{"data": "01/09/2026", "valor": "14,90"}])

    cdi = market.cdi_anual()

    assert cdi["valor"] == 14.9
    assert cdi["fonte"] == "BCB/SGS 4389"


def test_indicador_cai_no_padrao_quando_bcb_falha(dados_temp, rede):
    rede.rotas["bcdata.sgs.432"] = RuntimeError("rede fora")

    selic = market.selic_meta()

    assert selic["valor"] == 15.0
    assert selic["fonte"] == "padrao"
    assert "rede fora" in selic["erro"]


def test_ipca_acumulado_compoe_o_periodo(dados_temp, rede):
    rede.rotas["bcdata.sgs.433"] = RespostaFalsa(
        [{"data": "01/01/2026", "valor": "1,00"}, {"data": "01/02/2026", "valor": "1,00"}]
    )

    ipca = market.ipca_acumulado(date(2026, 1, 1))

    assert abs(ipca["fator"] - 1.0201) < 1e-9
    assert ipca["meses"] == 2
    assert rede.chamadas[0]["params"]["dataInicial"] == "01/01/2026"


def test_ipca_acumulado_aplica_o_primeiro_mes_pro_rata(dados_temp, rede):
    """Aplicação em 04/02 só é corrigida por 25 dos 28 dias de fevereiro."""
    rede.rotas["bcdata.sgs.433"] = RespostaFalsa(
        [{"data": "01/02/2026", "valor": "1,00"}, {"data": "01/03/2026", "valor": "1,00"}]
    )

    ipca = market.ipca_acumulado(date(2026, 2, 4))

    assert abs(ipca["fator"] - 1.01 ** (25 / 28) * 1.01) < 1e-9
    assert ipca["meses"] == 2


def test_ipca_12m_compoe_doze_meses(dados_temp, rede):
    rede.rotas["bcdata.sgs.433"] = RespostaFalsa([{"valor": "0,50"}] * 12)

    ipca = market.ipca_12m()

    assert 6.1 < ipca["valor"] < 6.2


def test_ipca_devolve_nulos_quando_falha(dados_temp, rede):
    rede.rotas["bcdata.sgs.433"] = RuntimeError("504")

    assert market.ipca_12m()["valor"] is None
    assert market.ipca_acumulado(date(2026, 1, 1))["fator"] is None


def test_indices_ignoram_o_indisponivel(dados_temp, rede):
    rede.rotas["%5EBVSP"] = chart_yahoo(145000, 144000, "Ibovespa")
    rede.rotas["^BVSP"] = chart_yahoo(145000, 144000, "Ibovespa")
    rede.rotas["^IFIX"] = RuntimeError("sem dados")

    indices = market.indices_mercado()

    assert indices["ibovespa"]["valor"] == 145000
    assert abs(indices["ibovespa"]["variacao_dia_pct"] - 0.6944) < 0.001
    assert "ifix" not in indices


def test_cenario_macro_reune_tudo(dados_temp, mercado_padrao):
    mercado_padrao.rotas["^BVSP"] = chart_yahoo(145000, 144000, "Ibovespa")

    macro = market.cenario_macro()

    assert macro["cdi_anual_pct"]["valor"] == 15.0
    assert macro["selic_meta_pct"]["valor"] == 15.0
    assert macro["ipca_12m_pct"]["valor"] > 0
    assert macro["indices"]["ibovespa"]["valor"] == 145000
    assert macro["consultado_em"].startswith("20")

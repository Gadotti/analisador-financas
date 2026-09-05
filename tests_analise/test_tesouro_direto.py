"""Leitura das taxas e preços do Tesouro Transparente."""

import pytest

from analise import cache, tesouro_direto as td
from conftest import RespostaFalsa, csv_tesouro

# Dois pregões, do mais novo para o mais antigo, como o arquivo oficial vem.
# 02/01/2025 é uma quinta; 04/01/2025, um sábado sem pregão.
ARQUIVO = (
    "Tesouro Selic;01/03/2029;03/09/2026;0,03;0,04;19800,36;19785,18;19785,18",
    "Tesouro Prefixado;01/01/2031;03/09/2026;14,22;14,34;565,63;562,79;562,79",
    "Tesouro IPCA+ com Juros Semestrais;15/05/2035;03/09/2026;7,73;7,85;4338,38;4305,64;4305,64",
    "Tesouro Educa+;15/12/2040;03/09/2026;7,10;7,22;1000,00;995,00;995,00",
    "Tesouro Selic;01/03/2029;02/01/2025;0,13;0,14;15745,70;15731,90;15731,90",
    "Tesouro Prefixado;01/01/2031;02/01/2025;15,60;15,72;421,94;419,80;419,80",
)

SELIC_2029 = {
    "id": "t1",
    "indexador": "SELIC",
    "pagamento_juros": "vencimento",
    "data_vencimento": "2029-03-01",
    "data_aplicacao": "2025-01-02",
}


@pytest.fixture
def tesouro(rede, dados_temp):
    """Rede com o arquivo do Tesouro e cache isolado num diretório temporário."""
    rede.rotas["precotaxatesourodireto"] = csv_tesouro(*ARQUIVO)
    return rede


# ─────────────────────────────────────────────
# Parsing
# ─────────────────────────────────────────────

def test_linha_converte_numeros_e_datas_no_formato_brasileiro():
    linha = td._linha("Tesouro Prefixado;01/01/2031;02/01/2025;15,60;15,72;1.421,94;419,80;419,80")

    assert linha["tipo"] == "Tesouro Prefixado"
    assert linha["vencimento"].isoformat() == "2031-01-01"
    assert linha["data_base"].isoformat() == "2025-01-02"
    assert linha["taxa_compra"] == 15.60
    assert linha["pu_compra"] == 1421.94


@pytest.mark.parametrize(
    "bruta",
    [
        "Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manha;Taxa Venda Manha;"
        "PU Compra Manha;PU Venda Manha;PU Base Manha",
        "Tesouro Selic;01/03/2029;03/09/2026;0,03",          # linha cortada ao meio
        "Tesouro Selic;xx/xx/xxxx;03/09/2026;0,03;0,04;1;1;1",  # data ilegivel
        "",
    ],
)
def test_linha_descarta_o_que_nao_e_dado(bruta):
    assert td._linha(bruta) is None


# ─────────────────────────────────────────────
# Cotação do dia
# ─────────────────────────────────────────────

def test_cotacoes_pegam_so_o_pregao_mais_recente(tesouro):
    do_dia = td.cotacoes(usar_cache=False)

    assert {c["data_base"] for c in do_dia.values()} == {"2026-09-03"}
    assert "SELIC:vencimento:2029-03-01" in do_dia
    assert do_dia["SELIC:vencimento:2029-03-01"]["pu_venda"] == 19785.18


def test_cotacoes_ignoram_familias_que_a_carteira_nao_cadastra(tesouro):
    """Educa+ e Renda+ existem no arquivo, mas não são tipos da carteira."""
    do_dia = td.cotacoes(usar_cache=False)

    assert not any("Educa" in chave for chave in do_dia)
    assert len(do_dia) == 3


def test_cotacao_de_casa_pelo_indexador_prazo_e_cupom(tesouro):
    do_dia = td.cotacoes(usar_cache=False)
    semestral = {
        "indexador": "IPCA",
        "pagamento_juros": "semestral",
        "data_vencimento": "2035-05-15",
    }

    assert td.cotacao_de(do_dia, semestral)["taxa_venda_pct"] == 7.85
    # Mesmo prazo e indexador, mas sem cupom: é outro papel.
    assert td.cotacao_de(do_dia, {**semestral, "pagamento_juros": "vencimento"}) is None


def test_cotacoes_usam_a_taxa_de_revenda_e_nao_a_de_compra(tesouro):
    """A troca das duas colunas inverteria o resultado — vale travar aqui.

    Nos metadados oficiais, "Venda" é a ponta em que o investidor revende ao
    Tesouro, e é ela que vale para marcar a posição a mercado.
    """
    do_dia = td.cotacoes(usar_cache=False)
    prefixado = do_dia["PRE:vencimento:2031-01-01"]

    assert prefixado["taxa_venda_pct"] == 14.34
    assert prefixado["pu_venda"] == 562.79


def test_cotacoes_sobrevivem_a_queda_da_fonte(tesouro):
    tesouro.rotas["precotaxatesourodireto"] = RespostaFalsa(texto="", status=503)

    assert "erro" in td.cotacoes(usar_cache=False)


def test_cotacoes_vao_para_o_cache(tesouro):
    td.cotacoes()
    chamadas = len(tesouro.chamadas)

    assert td.cotacoes()["PRE:vencimento:2031-01-01"]["pu_venda"] == 562.79
    assert len(tesouro.chamadas) == chamadas, "a segunda leitura nao deve ir a rede"


# ─────────────────────────────────────────────
# Taxa travada na compra
# ─────────────────────────────────────────────

def test_taxa_na_compra_usa_a_ponta_em_que_o_investidor_compra(tesouro):
    """É a `Taxa Compra`, não a `Taxa Venda` — a inversão encareceria o papel."""
    achados = td.taxas_na_compra([SELIC_2029], usar_cache=False)

    assert achados["t1"]["taxa_pct"] == 0.13
    assert achados["t1"]["pu_compra"] == 15745.70
    assert achados["t1"]["data_base"] == "2025-01-02"


def test_compra_em_dia_sem_pregao_cai_no_pregao_anterior(tesouro):
    """Aplicação num sábado usa a taxa da sexta, que foi a que valeu na ordem."""
    sabado = {**SELIC_2029, "data_aplicacao": "2025-01-04"}
    achados = td.taxas_na_compra([sabado], usar_cache=False)

    assert achados["t1"]["data_base"] == "2025-01-02"


def test_compra_anterior_ao_arquivo_nao_inventa_taxa(tesouro):
    antiga = {**SELIC_2029, "data_aplicacao": "2020-01-02"}

    assert td.taxas_na_compra([antiga], usar_cache=False) == {}


def test_taxa_na_compra_nao_expira_no_cache(tesouro):
    """Pregão fechado não muda mais: uma busca por título, e nunca de novo."""
    td.taxas_na_compra([SELIC_2029])
    chamadas = len(tesouro.chamadas)

    assert td.taxas_na_compra([SELIC_2029])["t1"]["taxa_pct"] == 0.13
    assert len(tesouro.chamadas) == chamadas
    assert cache.obter(td._chave_compra(SELIC_2029), cache.SEM_EXPIRAR) is not None


def test_uma_leitura_do_arquivo_resolve_a_carteira_inteira(tesouro):
    prefixado = {
        "id": "t2",
        "indexador": "PRE",
        "pagamento_juros": "vencimento",
        "data_vencimento": "2031-01-01",
        "data_aplicacao": "2025-01-02",
    }
    achados = td.taxas_na_compra([SELIC_2029, prefixado], usar_cache=False)

    assert set(achados) == {"t1", "t2"}
    assert achados["t2"]["taxa_pct"] == 15.60
    assert len(tesouro.chamadas) == 1


def test_combinacao_sem_titulo_equivalente_e_ignorada(tesouro):
    """Selic com cupom não existe no Tesouro Direto — não há o que buscar."""
    inexistente = {**SELIC_2029, "pagamento_juros": "semestral"}

    assert td.taxas_na_compra([inexistente], usar_cache=False) == {}
    assert tesouro.chamadas == []


def test_falha_de_rede_devolve_o_que_ja_estava_em_cache(tesouro):
    td.taxas_na_compra([SELIC_2029])
    tesouro.rotas["precotaxatesourodireto"] = RespostaFalsa(texto="", status=500)
    outro = {**SELIC_2029, "id": "novo", "data_vencimento": "2031-03-01"}

    assert td.taxas_na_compra([SELIC_2029])["t1"]["taxa_pct"] == 0.13
    assert td.taxas_na_compra([outro]) == {}, "sem rede e sem cache, nao ha o que devolver"


def test_posicoes_no_mesmo_papel_e_no_mesmo_dia_dividem_a_busca(tesouro):
    """A chave do cache é o título comprado, não a posição — dois aportes
    iguais no mesmo pregão custam uma leitura só."""
    segunda = {**SELIC_2029, "id": "t9"}
    td.taxas_na_compra([SELIC_2029])
    chamadas = len(tesouro.chamadas)

    assert td.taxas_na_compra([segunda])["t9"]["taxa_pct"] == 0.13
    assert len(tesouro.chamadas) == chamadas

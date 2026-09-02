"""Unificação das variantes de nome de gestora, sem consultar a IA."""

from analise import gestoras


def canonicos(*nomes):
    """Conjunto de nomes canônicos resultantes — o que vira linha na alocação."""
    return set(gestoras.unificar_variantes(nomes).values())


def test_parentese_explicativo_nao_separa_a_mesma_gestora():
    mapa = gestoras.unificar_variantes([
        "Pátria Investimentos",
        "Pátria Investimentos (gestão transferida da Credit Suisse em jul/2024)",
    ])

    assert set(mapa.values()) == {"Pátria Investimentos"}


def test_razao_social_diferente_da_mesma_casa_vira_um_grupo():
    mapa = gestoras.unificar_variantes([
        "XP Asset Management (XP Vista)",
        "XP Vista Asset Management (administração BTG Pactual)",
    ])

    assert set(mapa.values()) == {"XP Asset Management"}, "o rótulo mais curto do grupo"


def test_acento_e_caixa_nao_criam_grupos_distintos():
    assert canonicos("Pátria Investimentos", "PATRIA INVESTIMENTOS") == {"Pátria Investimentos"}


def test_gestoras_diferentes_continuam_separadas():
    assert canonicos("TRX Investimentos", "Tivio Capital", "Kinea") == {
        "TRX Investimentos",
        "Tivio Capital",
        "Kinea",
    }


def test_prefixo_e_por_token_inteiro():
    assert canonicos("XP Asset", "XPTO Gestora") == {"XP Asset", "XPTO Gestora"}


def test_nome_so_de_termos_genericos_nao_engole_os_demais():
    assert canonicos("Gestora de Recursos Ltda", "Kinea Investimentos") == {
        "Gestora de Recursos Ltda",
        "Kinea Investimentos",
    }


def test_nomes_vazios_ficam_de_fora_do_mapa():
    assert gestoras.unificar_variantes(["", "   ", None]) == {}


def test_chave_descarta_conectivos_e_razao_social():
    assert gestoras.chave_gestora("Banco do Brasil Asset Management S.A.") == ("banco", "brasil")

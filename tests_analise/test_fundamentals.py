"""Métricas agregadas a partir das fichas levantadas pela IA."""

import copy

from analise import fundamentals


def snapshot_dois(snapshot_exemplo):
    """Dois FIIs (30 mil e 10 mil) numa carteira de 50 mil.

    Os 10 mil restantes não têm ficha — é o que exercita a base da carteira
    nos recortes e a linha "não coberto".
    """
    base = copy.deepcopy(snapshot_exemplo)
    base["totais"]["valor_atual"] = 50000.0
    base["posicoes"] = [
        {
            "id": "a1",
            "tipo": "fii",
            "ticker": "MXRF11",
            "valor_atual": 30000.0,
            "valor_investido": 25000.0,
            "peso_pct": 60.0,
            "resultado_pct": 10.0,
            "preco_atual": 12.0,
            "preco_medio": 10.0,
            "quantidade": 2500.0,
        },
        {
            "id": "b2",
            "tipo": "fii",
            "ticker": "HGLG11",
            "valor_atual": 10000.0,
            "valor_investido": 10428.0,
            "peso_pct": 20.0,
            "resultado_pct": -5.0,
            "preco_atual": 150.0,
            "preco_medio": 158.0,
            "quantidade": 66.0,
        },
    ]
    return base


def ia_dois(mxrf=None, hglg=None):
    return {
        "ativos": [
            {
                "ticker": "MXRF11",
                "nome": "Maxi Renda",
                "classificacao": "papel",
                "segmento": "Recebíveis",
                "gestora": "XP Asset",
                "p_vp": 1.0,
                "dy_12m_pct": 12.0,
                **(mxrf or {}),
            },
            {
                "ticker": "HGLG11",
                "nome": "CSHG Logística",
                "classificacao": "tijolo",
                "segmento": "Logística",
                "gestora": "CSHG",
                "p_vp": 0.8,
                "dy_12m_pct": 8.0,
                **(hglg or {}),
            },
        ]
    }


def test_sem_ia_ou_sem_ativos_devolve_none(snapshot_exemplo):
    assert fundamentals.consolidar(snapshot_exemplo, None) is None
    assert fundamentals.consolidar(snapshot_exemplo, {"ativos": []}) is None


def test_nenhuma_ficha_casa_com_posicao(snapshot_exemplo):
    assert fundamentals.consolidar(snapshot_exemplo, {"ativos": [{"ticker": "OUTRO11"}]}) is None


def test_medias_ponderadas_pelo_valor_de_mercado(snapshot_exemplo):
    f = fundamentals.consolidar(snapshot_dois(snapshot_exemplo), ia_dois())

    # (1.00x30000 + 0.80x10000) / 40000 = 0.95
    assert f["metricas"]["p_vp_medio"] == 0.95
    # (12x30000 + 8x10000) / 40000 = 11
    assert f["metricas"]["dy_medio_pct"] == 11.0
    assert f["valor_renda_variavel"] == 40000


def test_yoc_reescala_o_dy_pela_razao_entre_os_precos(snapshot_exemplo):
    fichas = fundamentals.consolidar(snapshot_dois(snapshot_exemplo), ia_dois())["fichas"]
    por_ticker = {f["ticker"]: f for f in fichas}

    # Comprado a 10,00 e cotado a 12,00: 12% x 12/10 = 14,4% sobre o custo.
    assert por_ticker["MXRF11"]["yoc_12m_pct"] == 14.4
    # Comprado acima da cotação de hoje, o YoC fica abaixo do DY: 8% x 150/158.
    assert por_ticker["HGLG11"]["yoc_12m_pct"] == 7.59
    assert por_ticker["MXRF11"]["dy_12m_pct"] == 12.0, "o DY de mercado nao muda"


def test_yoc_medio_pondera_pelo_valor_investido(snapshot_exemplo):
    m = fundamentals.consolidar(snapshot_dois(snapshot_exemplo), ia_dois())["metricas"]

    # (14.4x25000 + 7.59x10428) / 35428 = 12.397...
    assert m["yoc_medio_pct"] == 12.4
    assert m["yoc_cobertura"] == "2/2"
    assert m["dy_medio_pct"] == 11.0, "a media de mercado segue na base da cotacao"


def test_yoc_ausente_quando_falta_cotacao(snapshot_exemplo):
    base = snapshot_dois(snapshot_exemplo)
    base["posicoes"][1]["preco_atual"] = None

    f = fundamentals.consolidar(base, ia_dois())

    assert f["fichas"][1]["yoc_12m_pct"] is None
    assert f["metricas"]["yoc_cobertura"] == "1/2"
    assert f["metricas"]["yoc_medio_pct"] == 14.4


def test_yoc_ausente_quando_a_ia_nao_informou_o_dy(snapshot_exemplo):
    f = fundamentals.consolidar(
        snapshot_dois(snapshot_exemplo), ia_dois(hglg={"dy_12m_pct": None})
    )

    assert f["fichas"][1]["yoc_12m_pct"] is None
    assert f["metricas"]["yoc_cobertura"] == "1/2"


def test_renda_estimada_anual_e_mensal(snapshot_exemplo):
    f = fundamentals.consolidar(snapshot_dois(snapshot_exemplo), ia_dois())

    # 30000x12% + 10000x8% = 4400
    assert f["metricas"]["renda_anual_estimada"] == 4400
    assert f["metricas"]["renda_mensal_estimada"] == 366.67


def test_cobertura_informa_indicadores_ausentes(snapshot_exemplo):
    f = fundamentals.consolidar(
        snapshot_dois(snapshot_exemplo), ia_dois(hglg={"p_vp": None, "dy_12m_pct": None})
    )

    assert f["metricas"]["p_vp_cobertura"] == "1/2"
    assert f["metricas"]["dy_cobertura"] == "1/2"
    assert f["metricas"]["p_vp_medio"] == 1.0
    assert f["metricas"]["renda_anual_estimada"] == 3600


def test_extremos_de_valuation_e_yield(snapshot_exemplo):
    m = fundamentals.consolidar(snapshot_dois(snapshot_exemplo), ia_dois())["metricas"]

    assert m["maior_desconto"] == "HGLG11"
    assert m["maior_agio"] == "MXRF11"
    assert m["maior_dy"] == "MXRF11"
    assert m["menor_dy"] == "HGLG11"
    assert m["com_desconto"] == 1
    assert m["com_agio"] == 0, "P/VP exatamente 1,00 não é ágio"


def test_agrupamentos_ordenados_por_valor(snapshot_exemplo):
    f = fundamentals.consolidar(snapshot_dois(snapshot_exemplo), ia_dois())

    assert [g["nome"] for g in f["por_classificacao"]] == ["Papel", "Tijolo"]
    assert f["por_segmento"][0]["nome"] == "Recebíveis"
    assert f["por_gestora"][0]["ativos"] == ["MXRF11"]


def test_peso_dos_recortes_e_sobre_a_carteira_inteira(snapshot_exemplo):
    f = fundamentals.consolidar(snapshot_dois(snapshot_exemplo), ia_dois())

    # 30000 / 50000 — e não 30000 / 40000, que seria a base da renda variável.
    assert f["por_segmento"][0]["peso_pct"] == 60.0
    assert f["valor_total_carteira"] == 50000.0
    assert sum(g["peso_pct"] for g in f["por_segmento"]) == 80.0


def test_parte_da_carteira_sem_ficha_e_declarada(snapshot_exemplo):
    f = fundamentals.consolidar(snapshot_dois(snapshot_exemplo), ia_dois())

    assert f["nao_coberto"] == {"valor": 10000.0, "peso_pct": 20.0}


def test_grupo_carrega_o_tipo_dominante(snapshot_exemplo):
    f = fundamentals.consolidar(snapshot_dois(snapshot_exemplo), ia_dois())

    assert {g["nome"]: g["tipo"] for g in f["por_classificacao"]} == {
        "Papel": "fii",
        "Tijolo": "fii",
    }


def test_campo_vazio_vira_nao_informado(snapshot_exemplo):
    f = fundamentals.consolidar(snapshot_dois(snapshot_exemplo), ia_dois(hglg={"segmento": "  "}))

    assert any(g["nome"] == "Não informado" for g in f["por_segmento"])


def test_ficha_sem_posicao_correspondente(snapshot_exemplo):
    ia = ia_dois()
    ia["ativos"].append({"ticker": "xpml11", "p_vp": 1.0, "dy_12m_pct": 9.0})

    f = fundamentals.consolidar(snapshot_dois(snapshot_exemplo), ia)

    assert f["sem_posicao"] == ["XPML11"]
    assert len(f["fichas"]) == 2


def test_ficha_enriquecida_com_os_numeros_da_posicao(snapshot_exemplo):
    f = fundamentals.consolidar(snapshot_dois(snapshot_exemplo), ia_dois())
    mxrf = next(x for x in f["fichas"] if x["ticker"] == "MXRF11")

    assert mxrf["valor_atual"] == 30000
    assert mxrf["peso_pct"] == 60.0
    assert mxrf["quantidade"] == 2500
    assert mxrf["classificacao_rotulo"] == "Papel"


def test_classificacao_desconhecida_vira_travessao(snapshot_exemplo):
    f = fundamentals.consolidar(snapshot_dois(snapshot_exemplo), ia_dois(mxrf={"classificacao": "xyz"}))
    assert f["fichas"][0]["classificacao_rotulo"] == "—"


def test_cdb_nao_tem_ficha(snapshot_exemplo, ia_exemplo):
    f = fundamentals.consolidar(snapshot_exemplo, ia_exemplo)

    assert len(f["fichas"]) == 1
    assert f["fichas"][0]["ticker"] == "MXRF11"


def test_variantes_do_nome_da_gestora_viram_uma_linha_so(snapshot_exemplo):
    f = fundamentals.consolidar(
        snapshot_dois(snapshot_exemplo),
        ia_dois(
            mxrf={"gestora": "XP Asset Management (XP Vista)"},
            hglg={"gestora": "XP Vista Asset Management (administração BTG Pactual)"},
        ),
    )

    assert [g["nome"] for g in f["por_gestora"]] == ["XP Asset Management"]
    assert f["por_gestora"][0]["peso_pct"] == 80.0
    assert f["por_gestora"][0]["ativos"] == ["MXRF11", "HGLG11"]
    assert [ficha["gestora"] for ficha in f["fichas"]] == ["XP Asset Management"] * 2

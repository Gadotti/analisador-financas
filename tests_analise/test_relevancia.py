"""Seleção do que entra na mensagem curta do Telegram."""

import copy
from datetime import date

import pytest

from analise import estado_envio, gatilhos, mensagem, portfolio, relevancia

# 08/09/2026 é uma terça; 11/09/2026 é a sexta da mesma semana.
TERCA = date(2026, 9, 8)
SEXTA = date(2026, 9, 11)


def cfg(**blocos) -> dict:
    """Cadastro com o bloco do Telegram ajustado sobre os padrões."""
    return {"telegram": blocos}


def selecionar(snapshot, **kw):
    return relevancia.selecionar(snapshot, kw.pop("ia", None), kw.pop("fundamentos", None),
                                 kw.pop("config", None), hoje=kw.pop("hoje", TERCA), **kw)


def blocos_de(selecao) -> list[str]:
    return [item["bloco"] for item in selecao["itens"]]


def titulos_de(selecao, bloco) -> list[str]:
    return [i["titulo"] for i in selecao["itens"] if i["bloco"] == bloco]


@pytest.fixture
def calmo(snapshot_exemplo):
    """Snapshot sem nada que cruze limiar: dia de mensagem mínima."""
    base = copy.deepcopy(snapshot_exemplo)
    base["alertas"] = []
    base["totais"]["resultado_dia"] = 0.0
    base["posicoes"][0]["variacao_dia_pct"] = 0.2
    return base


# ─────────────────────────────────────────────
# O princípio: o limiar é que faz o bloco falar
# ─────────────────────────────────────────────

def test_dia_calmo_nao_produz_item_nenhum(calmo):
    selecao = selecionar(calmo)

    assert selecao["itens"] == []
    assert selecao["modo"] == "nada_novo"


def test_variacao_do_dia_entra_so_acima_do_limiar(calmo):
    calmo["totais"]["resultado_dia"] = 1000.0

    abaixo = selecionar(calmo, config=cfg(variacao_dia={"limiar_pct": 90.0}))
    acima = selecionar(calmo, config=cfg(variacao_dia={"limiar_pct": 1.0}))

    assert "variacao_dia" not in blocos_de(abaixo)
    assert "variacao_dia" in blocos_de(acima)


def test_interruptor_desligado_cala_o_bloco(snapshot_exemplo):
    ligado = selecionar(snapshot_exemplo)
    desligado = selecionar(snapshot_exemplo, config=cfg(alertas={"ativo": False}))

    assert "alertas" in blocos_de(ligado)
    assert "alertas" not in blocos_de(desligado)


# ─────────────────────────────────────────────
# Macro: a única comparação com o passado
# ─────────────────────────────────────────────

def macro_anterior(**valores) -> dict:
    return {chave: {"valor": v, "fonte": "BCB/SGS"} for chave, v in valores.items()}


def test_selic_que_mudou_entra_na_mensagem(calmo):
    selecao = selecionar(calmo, macro_anterior=macro_anterior(selic_meta_pct=15.25))

    titulos = titulos_de(selecao, "macro")
    assert titulos == ["Selic meta caiu para 15,00% a.a."]
    assert "Era 15,25% a.a." in selecao["itens"][0]["detalhe"]


def test_indicador_parado_nao_gera_item(calmo):
    selecao = selecionar(
        calmo,
        macro_anterior=macro_anterior(selic_meta_pct=15.0, cdi_anual_pct=14.9, ipca_12m_pct=4.2),
    )

    assert titulos_de(selecao, "macro") == []


def test_indicador_de_fonte_padrao_nao_inventa_mudanca(calmo):
    """O BCB fora do ar devolve um padrão embutido — comparar com ele mentiria."""
    calmo["macro"]["selic_meta_pct"] = {"valor": 15.0, "data": None, "fonte": "padrao"}

    selecao = selecionar(calmo, macro_anterior=macro_anterior(selic_meta_pct=13.0))

    assert titulos_de(selecao, "macro") == []


def test_sem_leitura_anterior_o_bloco_macro_fica_calado(calmo):
    assert titulos_de(selecionar(calmo), "macro") == []


def test_limiar_em_pontos_percentuais_filtra_ruido(calmo):
    anterior = macro_anterior(cdi_anual_pct=14.895)

    fino = selecionar(calmo, macro_anterior=anterior, config=cfg(macro={"limiar_pp": 0.001}))
    grosso = selecionar(calmo, macro_anterior=anterior, config=cfg(macro={"limiar_pp": 0.5}))

    assert titulos_de(fino, "macro")
    assert titulos_de(grosso, "macro") == []


def test_macro_comparavel_guarda_so_os_tres_indicadores(snapshot_exemplo):
    recorte = relevancia.macro_comparavel(snapshot_exemplo["macro"])

    assert set(recorte) == {"selic_meta_pct", "cdi_anual_pct", "ipca_12m_pct"}
    assert relevancia.macro_comparavel({}) is None


# ─────────────────────────────────────────────
# Posições em movimento
# ─────────────────────────────────────────────

def test_movimento_respeita_limiar_e_peso_minimo(calmo):
    calmo["posicoes"][0]["variacao_dia_pct"] = -4.0

    passa = selecionar(calmo, config=cfg(movimento={"limiar_pct": 3.0, "peso_minimo_pct": 3.0}))
    barrado = selecionar(calmo, config=cfg(movimento={"limiar_pct": 3.0, "peso_minimo_pct": 90.0}))

    assert titulos_de(passa, "movimento") == ["MXRF11 -4,0% no dia"]
    assert titulos_de(barrado, "movimento") == []


def test_movimento_ordena_pela_maior_variacao_e_respeita_o_teto(calmo):
    outra = copy.deepcopy(calmo["posicoes"][0])
    outra.update({"id": "c3", "descricao": "HGLG11", "ticker": "HGLG11", "variacao_dia_pct": -7.5})
    calmo["posicoes"][0]["variacao_dia_pct"] = -4.0
    calmo["posicoes"].append(outra)

    selecao = selecionar(calmo, config=cfg(movimento={"limiar_pct": 3.0, "max": 1}))

    assert titulos_de(selecao, "movimento") == ["HGLG11 -7,5% no dia"]


# ─────────────────────────────────────────────
# Calendário de renda fixa: marcos, não janela
# ─────────────────────────────────────────────

def test_vencimento_fala_no_marco_e_cala_fora_dele(calmo):
    cdb = calmo["posicoes"][1]

    cdb["dias_para_vencer"] = 15
    no_marco = selecionar(calmo)
    cdb["dias_para_vencer"] = 14
    fora = selecionar(calmo)

    assert titulos_de(no_marco, "calendario_rf") == ["CDB Inter 110% do CDI vence em 15 dia(s)"]
    assert titulos_de(fora, "calendario_rf") == []


def test_cupom_creditado_hoje_e_anunciado(calmo):
    calmo["posicoes"][1].update({
        "pagamento_juros": "mensal",
        "ultimo_pagamento": TERCA.isoformat(),
        "pagamentos_realizados": 8,
        "juros_recebidos_liquido": 812.34,
    })

    selecao = selecionar(calmo)

    assert titulos_de(selecao, "calendario_rf") == ["Cupom creditado — CDB Inter 110% do CDI"]
    assert "R$ 812,34" in selecao["itens"][0]["detalhe"]


def test_proximo_cupom_entra_quando_cai_num_marco(calmo):
    calmo["posicoes"][1].update({
        "pagamento_juros": "mensal",
        "proximo_pagamento": "2026-09-11",  # três dias depois de TERCA
    })

    selecao = selecionar(calmo)

    assert titulos_de(selecao, "calendario_rf") == ["CDB Inter 110% do CDI paga juros em 3 dia(s)"]


# ─────────────────────────────────────────────
# Alertas: piso de severidade e contagem do resto
# ─────────────────────────────────────────────

def test_alerta_abaixo_do_piso_vira_contagem_em_curso(snapshot_exemplo):
    selecao = selecionar(snapshot_exemplo, config=cfg(alertas={"severidade_minima": "alerta"}))

    assert titulos_de(selecao, "alertas") == []
    assert selecao["alertas_em_curso"] == 1


def test_alerta_publicado_nao_conta_como_em_curso(snapshot_exemplo):
    selecao = selecionar(snapshot_exemplo, config=cfg(alertas={"severidade_minima": "atencao"}))

    assert len(titulos_de(selecao, "alertas")) == 1
    assert selecao["alertas_em_curso"] == 0


# ─────────────────────────────────────────────
# Fatos e riscos da IA
# ─────────────────────────────────────────────

def test_fato_de_ativo_leve_nao_passa_o_piso_de_peso(calmo, ia_exemplo):
    ia_exemplo["fatos"][0]["severidade"] = "atencao"

    passa = selecionar(calmo, ia=ia_exemplo, config=cfg(fatos_ia={"peso_minimo_pct": 5.0}))
    barrado = selecionar(calmo, ia=ia_exemplo, config=cfg(fatos_ia={"peso_minimo_pct": 90.0}))

    assert titulos_de(passa, "fatos_ia") == ["[MXRF11] Distribuição mantida"]
    assert titulos_de(barrado, "fatos_ia") == []


def test_fato_setorial_sem_peso_no_ativo_nao_e_barrado_pelo_piso(calmo, ia_exemplo):
    """Um fato sobre algo fora da carteira (setor, fundo comparável) não tem
    peso a medir — barrá-lo pelo piso descartaria uma leitura relevante que
    nunca teve como passar, só por o campo não ser um ticker da carteira."""
    ia_exemplo["fatos"][0].update({
        "ativo": "Setor de papel (referência de mercado)",
        "severidade": "atencao",
    })

    selecao = selecionar(calmo, ia=ia_exemplo, config=cfg(fatos_ia={"peso_minimo_pct": 50.0}))

    assert titulos_de(selecao, "fatos_ia") == [
        "[Setor de papel (referência de mercado)] Distribuição mantida"
    ]


def test_fato_de_ativo_real_com_peso_baixo_continua_barrado(calmo, ia_exemplo):
    """O piso de peso continua valendo quando o ativo está de fato na carteira."""
    ia_exemplo["fatos"][0]["severidade"] = "atencao"
    calmo["posicoes"][0]["peso_pct"] = 1.0

    selecao = selecionar(calmo, ia=ia_exemplo, config=cfg(fatos_ia={"peso_minimo_pct": 5.0}))

    assert titulos_de(selecao, "fatos_ia") == []


def test_fato_informativo_nao_passa_o_piso_de_severidade(calmo, ia_exemplo):
    selecao = selecionar(calmo, ia=ia_exemplo, config=cfg(fatos_ia={"severidade_minima": "atencao"}))

    assert titulos_de(selecao, "fatos_ia") == []


def test_risco_entra_com_os_ativos_no_titulo(calmo, ia_exemplo):
    selecao = selecionar(calmo, ia=ia_exemplo, config=cfg(riscos_ia={"severidade_minima": "info"}))

    assert titulos_de(selecao, "riscos_ia") == ["Concentração em um único FII (MXRF11)"]


# ─────────────────────────────────────────────
# Deduplicação: não repetir um achado inalterado
# ─────────────────────────────────────────────

def test_alerta_ja_enviado_some_da_selecao_mas_conta_em_curso(snapshot_exemplo):
    alerta = snapshot_exemplo["alertas"][0]
    estado = {"alertas": [estado_envio.hash_alerta(alerta)], "riscos_ia": [], "fatos_ia": []}

    selecao = selecionar(snapshot_exemplo, estado_envio=estado)

    assert titulos_de(selecao, "alertas") == []
    assert selecao["alertas_em_curso"] == 1


def test_alerta_com_texto_novo_volta_a_ser_enviado(snapshot_exemplo):
    alerta = snapshot_exemplo["alertas"][0]
    estado = {"alertas": [estado_envio.hash_alerta(alerta)], "riscos_ia": [], "fatos_ia": []}
    alerta["descricao"] = "A posicao subiu para 60% da carteira."

    selecao = selecionar(snapshot_exemplo, estado_envio=estado)

    assert titulos_de(selecao, "alertas") == [alerta["titulo"]]


def test_risco_e_fato_ja_enviados_nao_repetem(calmo, ia_exemplo):
    estado = {
        "alertas": [],
        "riscos_ia": [estado_envio.hash_risco(ia_exemplo["riscos"][0])],
        "fatos_ia": [estado_envio.hash_fato(ia_exemplo["fatos"][0])],
    }

    selecao = selecionar(
        calmo, ia=ia_exemplo, config=cfg(riscos_ia={"severidade_minima": "info"}),
        estado_envio=estado,
    )

    assert titulos_de(selecao, "riscos_ia") == []
    assert titulos_de(selecao, "fatos_ia") == []


def test_sem_estado_envio_a_selecao_funciona_como_antes(snapshot_exemplo):
    """`estado_envio` é opcional — quem não o passa não perde nenhum item."""
    assert titulos_de(selecionar(snapshot_exemplo), "alertas") != []


def test_alerta_fora_do_teto_sobe_quando_o_de_cima_ja_foi_enviado(snapshot_exemplo):
    """Sem isso o primeiro alerta venceria a disputa pelo teto para sempre, e o
    segundo ficaria "em curso" mesmo sem nunca ter sido enviado."""
    primeiro = snapshot_exemplo["alertas"][0]
    segundo = {**primeiro, "titulo": "Concentracao em CDB Inter: 45.5%",
               "descricao": "Outra posicao.", "alvo": "CDB Inter"}
    snapshot_exemplo["alertas"] = [primeiro, segundo]
    estado = {"alertas": [estado_envio.hash_alerta(primeiro)], "riscos_ia": [], "fatos_ia": []}

    selecao = selecionar(snapshot_exemplo, config=cfg(alertas={"max": 1}), estado_envio=estado)

    assert titulos_de(selecao, "alertas") == [segundo["titulo"]]
    assert selecao["alertas_em_curso"] == 1


def test_risco_fora_do_teto_sobe_quando_o_de_cima_ja_foi_enviado(calmo, ia_exemplo):
    primeiro = ia_exemplo["riscos"][0]
    segundo = {**primeiro, "titulo": "Concentração setorial em recebíveis"}
    ia_exemplo["riscos"] = [primeiro, segundo]
    estado = {"alertas": [], "riscos_ia": [estado_envio.hash_risco(primeiro)], "fatos_ia": []}

    selecao = selecionar(
        calmo, ia=ia_exemplo,
        config=cfg(riscos_ia={"severidade_minima": "info", "max": 1}),
        estado_envio=estado,
    )

    assert titulos_de(selecao, "riscos_ia") == [f"{segundo['titulo']} (MXRF11)"]


def test_alerta_ja_enviado_nao_conta_como_pendente(snapshot_exemplo):
    """Sem essa distinção, "1 alerta em curso" parece uma fila parada quando na
    verdade é só o alerta ainda verdadeiro não se repetindo, de propósito."""
    alerta = snapshot_exemplo["alertas"][0]
    estado = {"alertas": [estado_envio.hash_alerta(alerta)], "riscos_ia": [], "fatos_ia": []}

    selecao = selecionar(snapshot_exemplo, estado_envio=estado)

    assert selecao["alertas_em_curso"] == 1
    assert selecao["alertas_pendentes"] == 0
    assert "ainda não enviado" not in mensagem.telegram_resumo(selecao)


def test_alerta_nunca_enviado_cortado_pelo_orcamento_conta_como_pendente(snapshot_exemplo):
    segundo = {
        **snapshot_exemplo["alertas"][0],
        "titulo": "Concentracao em CDB Inter: 45.5%",
        "descricao": "Outra posicao.",
        "alvo": "CDB Inter",
    }
    snapshot_exemplo["alertas"].append(segundo)

    selecao = selecionar(snapshot_exemplo, config=cfg(max_itens=0))

    assert selecao["alertas_em_curso"] == 2
    assert selecao["alertas_pendentes"] == 2
    assert "2 deles ainda não enviado(s)" in mensagem.telegram_resumo(selecao)


def test_fato_fora_do_teto_sobe_quando_o_de_cima_ja_foi_enviado(calmo, ia_exemplo):
    primeiro = {**ia_exemplo["fatos"][0], "severidade": "atencao"}
    segundo = {**primeiro, "titulo": "Novo comunicado ao mercado"}
    ia_exemplo["fatos"] = [primeiro, segundo]
    estado = {"alertas": [], "riscos_ia": [], "fatos_ia": [estado_envio.hash_fato(primeiro)]}

    selecao = selecionar(calmo, ia=ia_exemplo, config=cfg(fatos_ia={"max": 1}), estado_envio=estado)

    assert titulos_de(selecao, "fatos_ia") == [f"[{segundo['ativo']}] {segundo['titulo']}"]


# ─────────────────────────────────────────────
# Indicadores fora da faixa
# ─────────────────────────────────────────────

def fundamentos_falsos(**metricas) -> dict:
    padrao = {"p_vp_medio": 1.0, "dy_medio_pct": 10.0, "renda_mensal_estimada": 100.0}
    return {"fichas": [], "metricas": {**padrao, **metricas}}


def test_p_vp_fora_da_faixa_configurada_gera_item(calmo):
    dentro = selecionar(calmo, fundamentos=fundamentos_falsos(p_vp_medio=1.0))
    fora = selecionar(calmo, fundamentos=fundamentos_falsos(p_vp_medio=0.70))

    assert titulos_de(dentro, "indicadores") == []
    assert titulos_de(fora, "indicadores") == ["P/VP médio em 0,70 — desconto patrimonial"]


def test_dy_abaixo_do_piso_gera_item(calmo):
    selecao = selecionar(calmo, fundamentos=fundamentos_falsos(dy_medio_pct=6.0))

    assert titulos_de(selecao, "indicadores") == ["DY médio em 6,00% a.a."]


# ─────────────────────────────────────────────
# Rodízio determinístico
# ─────────────────────────────────────────────

def fichas_falsas(*tickers) -> dict:
    return {
        "fichas": [{"ticker": t, "segmento": "Logística", "comentario": "x"} for t in tickers],
        "metricas": {},
    }


def test_aprofundamento_muda_de_ativo_a_cada_dia(calmo):
    fundamentos = fichas_falsas("AAA11", "BBB11", "CCC11")

    escolhidos = [
        titulos_de(selecionar(calmo, fundamentos=fundamentos, hoje=date(2026, 9, dia)),
                   "aprofundamento")[0]
        for dia in (8, 9, 10)
    ]

    assert len(set(escolhidos)) == 3


def test_aprofundamento_cicla_a_carteira_inteira(calmo):
    fundamentos = fichas_falsas("AAA11", "BBB11")

    dia_8 = titulos_de(selecionar(calmo, fundamentos=fundamentos, hoje=date(2026, 9, 8)),
                       "aprofundamento")
    dia_10 = titulos_de(selecionar(calmo, fundamentos=fundamentos, hoje=date(2026, 9, 10)),
                        "aprofundamento")

    assert dia_8 == dia_10  # duas posições, ciclo de dois dias


def test_comentario_longo_e_cortado_no_fim_de_uma_frase(calmo):
    """O bloco de enchimento não pode ser o item mais longo da mensagem curta."""
    fundamentos = fichas_falsas("AAA11")
    fundamentos["fichas"][0]["comentario"] = (
        "Primeira frase curta. " + "Segunda frase bem mais longa que a primeira. " * 8
    )

    detalhe = selecionar(calmo, fundamentos=fundamentos)["itens"][0]["detalhe"]

    assert len(detalhe) <= gatilhos.LIMITE_COMENTARIO + 40
    assert detalhe.endswith(".")


def test_comentario_curto_passa_intacto(calmo):
    fundamentos = fichas_falsas("AAA11")
    fundamentos["fichas"][0]["comentario"] = "Fundo de logística com vacância baixa."

    detalhe = selecionar(calmo, fundamentos=fundamentos)["itens"][0]["detalhe"]

    assert detalhe.endswith("Fundo de logística com vacância baixa.")


def test_comentario_sem_pontuacao_ganha_reticencias(calmo):
    fundamentos = fichas_falsas("AAA11")
    fundamentos["fichas"][0]["comentario"] = "palavra " * 60

    detalhe = selecionar(calmo, fundamentos=fundamentos)["itens"][0]["detalhe"]

    assert detalhe.endswith("…")


def test_sem_ficha_nao_ha_aprofundamento(calmo):
    assert titulos_de(selecionar(calmo), "aprofundamento") == []


# ─────────────────────────────────────────────
# Orçamento e ordem
# ─────────────────────────────────────────────

def test_orcamento_corta_o_menos_relevante_primeiro(snapshot_exemplo):
    """O aprofundamento é o enchimento do dia calmo: sai antes do alerta."""
    fundamentos = fichas_falsas("AAA11")

    selecao = selecionar(snapshot_exemplo, fundamentos=fundamentos, config=cfg(max_itens=1))

    assert blocos_de(selecao) == ["alertas"]


def test_ordem_de_exibicao_segue_a_tabela_de_blocos(calmo):
    calmo["totais"]["resultado_dia"] = 1000.0
    calmo["posicoes"][0]["variacao_dia_pct"] = -6.0
    calmo["alertas"] = [{
        "severidade": "alerta", "titulo": "Teto do FGC estourado",
        "descricao": "Acima do limite.", "alvo": "Inter", "origem": "calculo",
    }]

    selecao = selecionar(calmo, macro_anterior=macro_anterior(selic_meta_pct=15.5))

    assert blocos_de(selecao) == ["variacao_dia", "macro", "movimento", "alertas"]


# ─────────────────────────────────────────────
# Cadência por data e piso de envio
# ─────────────────────────────────────────────

def test_resumo_da_ia_sai_so_nos_dias_configurados(calmo, ia_exemplo):
    na_sexta = selecionar(calmo, ia=ia_exemplo, hoje=SEXTA)
    na_terca = selecionar(calmo, ia=ia_exemplo, hoje=TERCA)

    assert na_sexta["resumo_ia"] == ia_exemplo["resumo"]
    assert na_terca["resumo_ia"] is None


def test_fechamento_semanal_sai_so_no_dia_configurado(calmo):
    assert selecionar(calmo, hoje=SEXTA)["semanal"] is not None
    assert selecionar(calmo, hoje=TERCA)["semanal"] is None


def test_agenda_semanal_lista_o_que_vence_no_proximo_mes(calmo):
    calmo["posicoes"][1].update({"dias_para_vencer": 20, "data_vencimento": "2026-10-01"})

    agenda = selecionar(calmo, hoje=SEXTA)["semanal"]["agenda"]

    assert [(a["descricao"], a["verbo"]) for a in agenda] == [
        ("CDB Inter 110% do CDI", "vence")
    ]


def test_so_se_relevante_dispensa_o_envio_do_dia_calmo(calmo):
    padrao = selecionar(calmo)
    exigente = selecionar(calmo, config=cfg(so_se_relevante=True))

    assert padrao["vale_enviar"] is True
    assert exigente["vale_enviar"] is False


# ─────────────────────────────────────────────
# Configuração parcial no cadastro
# ─────────────────────────────────────────────

def test_bloco_parcial_no_cadastro_nao_apaga_os_padroes():
    completo = portfolio.telegram_do_cadastro({"movimento": {"limiar_pct": 9.0}})

    assert completo["movimento"] == {
        "ativo": True, "limiar_pct": 9.0, "peso_minimo_pct": 3.0, "max": 3
    }
    assert completo["max_itens"] == portfolio.TELEGRAM_PADRAO["max_itens"]


def test_config_padrao_nao_compartilha_o_bloco_aninhado():
    uma = portfolio.config_padrao()
    outra = portfolio.config_padrao()

    uma["telegram"]["movimento"]["limiar_pct"] = 99.0

    assert outra["telegram"]["movimento"]["limiar_pct"] == 3.0
    assert portfolio.TELEGRAM_PADRAO["movimento"]["limiar_pct"] == 3.0


# ─────────────────────────────────────────────
# Renderização da mensagem curta
# ─────────────────────────────────────────────

def test_mensagem_do_dia_calmo_e_o_estado_e_o_rodape(calmo):
    saida = mensagem.telegram_resumo(selecionar(calmo))

    assert saida.startswith("📊 <b>R$ 22.000,00</b>")
    assert "+10,00% acumulado" in saida
    assert "não é recomendação de investimento" in saida
    assert saida.count("\n") < 6


def test_texto_da_ia_e_escapado_na_mensagem_curta(calmo, ia_exemplo):
    ia_exemplo["fatos"][0].update({"titulo": "Emissão <b>nova</b> & maior", "severidade": "alerta"})

    saida = mensagem.telegram_resumo(selecionar(calmo, ia=ia_exemplo))

    assert "Emissão &lt;b&gt;nova&lt;/b&gt; &amp; maior" in saida
    assert "<b>nova</b>" not in saida


def test_contagem_de_alertas_em_curso_aparece_na_mensagem(snapshot_exemplo):
    selecao = selecionar(snapshot_exemplo, config=cfg(alertas={"severidade_minima": "alerta"}))

    assert "1 alerta(s) em curso" in mensagem.telegram_resumo(selecao)


def test_mensagem_curta_cabe_no_limite_do_telegram(snapshot_exemplo, ia_exemplo):
    longo = copy.deepcopy(snapshot_exemplo)
    longo["alertas"] = [
        {
            "severidade": "alerta",
            "titulo": f"Alerta {i} " + "x" * 200,
            "descricao": "y" * 900,
            "alvo": "",
            "origem": "calculo",
        }
        for i in range(12)
    ]

    saida = mensagem.telegram_resumo(
        selecionar(longo, ia=ia_exemplo, config=cfg(max_itens=12, alertas={"max": 12}))
    )

    assert mensagem._unidades_utf16(saida) <= mensagem.LIMITE_TELEGRAM
    assert "não é recomendação de investimento" in saida


def test_leitura_herdada_e_marcada_na_mensagem_curta(calmo, ia_exemplo):
    ia_exemplo["_meta"]["gerado_em"] = "2026-08-20T09:00:00"

    saida = mensagem.telegram_resumo(selecionar(calmo, ia=ia_exemplo))

    assert "Leitura de IA herdada de 20/08/2026 às 09:00" in saida

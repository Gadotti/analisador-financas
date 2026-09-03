"""Formatação do relatório para terminal e Telegram."""

import copy
import re

from analise import fundamentals, report


def fundamentos(snapshot_exemplo, ia_exemplo):
    return fundamentals.consolidar(snapshot_exemplo, ia_exemplo)


# ─────────────────────────────────────────────
# Terminal
# ─────────────────────────────────────────────


def test_relatorio_minimo_sem_ia(snapshot_exemplo):
    saida = report.texto(snapshot_exemplo)

    assert "RELATÓRIO DE CARTEIRA" in saida
    assert "01/09/2026 às 10:30" in saida
    assert re.search(r"Valor de mercado \.+ R\$ 22\.000,00", saida)
    assert re.search(r"Resultado acumulado \.+ R\$ 2\.000,00\s+\(\+10,00%\)", saida)
    assert "ALOCAÇÃO" in saida
    assert "POSIÇÕES" in saida
    assert "CONTEXTO DE MERCADO" in saida
    assert "não constitui recomendação de investimento" in saida


def test_emissor_de_renda_fixa_sai_mesmo_sem_ia(snapshot_exemplo):
    saida = report.texto(snapshot_exemplo)

    assert "Por emissor de renda fixa (% da carteira)" in saida
    assert "Inter" in saida
    assert "4% do FGC" in saida


def test_cdb_de_juros_mensais_ganha_uma_linha_de_cupons(snapshot_exemplo):
    base = copy.deepcopy(snapshot_exemplo)
    cdb = next(p for p in base["posicoes"] if p["tipo"] == "cdb")
    cdb.update({
        "pagamento_juros": "mensal",
        "pagamentos_realizados": 8,
        "proximo_pagamento": "2026-10-02",
        "juros_recebidos_liquido": 812.34,
    })

    saida = report.texto(base)

    assert "juros mensais · 8 pagamento(s) · R$ 812,34 líquidos recebidos" in saida
    assert "próximo em 02/10/2026" in saida


def test_cdb_de_juros_mensais_no_vencimento_nao_tem_proximo(snapshot_exemplo):
    base = copy.deepcopy(snapshot_exemplo)
    cdb = next(p for p in base["posicoes"] if p["tipo"] == "cdb")
    cdb.update({
        "pagamento_juros": "mensal",
        "pagamentos_realizados": 24,
        "proximo_pagamento": None,
        "juros_recebidos_liquido": 2100.0,
    })

    assert "sem novos pagamentos" in report.texto(base)


def test_emissor_acima_do_fgc_e_marcado(snapshot_exemplo):
    base = copy.deepcopy(snapshot_exemplo)
    base["emissores_renda_fixa"][0]["acima_do_fgc"] = True

    assert "acima do FGC" in report.texto(base)


def test_recortes_declaram_a_base_e_o_que_nao_cobrem(snapshot_exemplo, ia_exemplo):
    saida = report.texto(snapshot_exemplo, ia_exemplo, fundamentos(snapshot_exemplo, ia_exemplo))

    assert "Por segmento (% da carteira)" in saida
    assert "(renda variável)" not in saida
    # O CDB é 45,45% da carteira e não tem ficha em nenhum recorte.
    assert re.search(r"Sem ficha \(renda fixa\)\s+45,5%\s+R\$ 10\.000,00", saida)


def test_sem_ia_nao_inventa_secoes(snapshot_exemplo):
    saida = report.texto(snapshot_exemplo)

    assert "LEITURA DA CARTEIRA" not in saida
    assert "ANÁLISE POR ATIVO" not in saida
    assert "FATOS RECENTES" not in saida


def test_relatorio_completo_com_ia(snapshot_exemplo, ia_exemplo):
    saida = report.texto(snapshot_exemplo, ia_exemplo, fundamentos(snapshot_exemplo, ia_exemplo))

    assert "Carteira concentrada em um FII de papel" in saida
    assert "INDICADORES DA RENDA VARIÁVEL" in saida
    assert re.search(r"P/VP médio ponderado \.+ 0,98", saida)
    assert "DY médio ponderado" in saida
    assert "Renda estimada" in saida
    assert "▸ MXRF11 — Maxi Renda FII" in saida
    assert "LEITURA DA CARTEIRA" in saida
    assert "PONTOS DE OBSERVAÇÃO" in saida
    assert "Análise gerada por claude-opus-5 (effort medium) · 6 buscas web" in saida


def test_tabela_distingue_cdb_de_renda_variavel(snapshot_exemplo):
    saida = report.texto(snapshot_exemplo)

    assert "[ FII] MXRF11" in saida
    assert "[ CDB] Inter" in saida
    assert "1000 × R$ 12,00 · PM R$ 10,00" in saida
    assert "Inter · 04/01/2027 · vence em 490 dias" in saida


def test_cotacao_ausente_aparece_na_linha(snapshot_exemplo):
    snapshot = copy.deepcopy(snapshot_exemplo)
    snapshot["posicoes"][0]["preco_atual"] = None
    assert "sem cotação" in report.texto(snapshot)


def test_cdb_vencido_e_marcado(snapshot_exemplo):
    snapshot = copy.deepcopy(snapshot_exemplo)
    snapshot["posicoes"][1]["vencido"] = True
    assert "VENCIDO" in report.texto(snapshot)


def test_variacao_do_dia_omitida_quando_zero(snapshot_exemplo):
    snapshot = copy.deepcopy(snapshot_exemplo)
    snapshot["totais"]["resultado_dia"] = 0
    assert "Variação do dia" not in report.texto(snapshot)


def test_ibovespa_formatado(snapshot_exemplo):
    # 145200.5 arredonda para 145200: o Python usa arredondamento bancário.
    assert "Ibovespa 145.200 pts (+0,42% no dia)" in report.texto(snapshot_exemplo)


def test_marca_a_leitura_herdada_de_outra_data(snapshot_exemplo, ia_exemplo):
    """Herdada de outro dia, a leitura não pode passar por recém-feita."""
    ia = {**ia_exemplo, "_meta": {**ia_exemplo["_meta"], "gerado_em": "2026-08-28T09:00:00"}}

    assert "Leitura herdada da análise de 28/08/2026 às 09:00" in report.texto(snapshot_exemplo, ia)
    assert "Leitura herdada" in report.telegram(snapshot_exemplo, ia)


def test_leitura_do_proprio_dia_nao_e_marcada(snapshot_exemplo, ia_exemplo):
    assert "Leitura herdada" not in report.texto(snapshot_exemplo, ia_exemplo)
    assert "Leitura herdada" not in report.telegram(snapshot_exemplo, ia_exemplo)


def test_linhas_nao_estouram_a_largura(snapshot_exemplo, ia_exemplo):
    saida = report.texto(snapshot_exemplo, ia_exemplo, fundamentos(snapshot_exemplo, ia_exemplo))
    excedentes = [l for l in saida.split("\n") if len(l) > report.LARGURA + 25]
    assert excedentes == []


# ─────────────────────────────────────────────
# Telegram
# ─────────────────────────────────────────────


def test_mensagem_basica_em_html(snapshot_exemplo):
    msg = report.telegram(snapshot_exemplo)

    assert "<b>Relatório de Carteira</b>" in msg
    assert "01/09/2026 — 10:30" in msg
    assert "<b>R$ 22.000,00</b>" in msg
    assert "ALOCAÇÃO" in msg
    assert "ALERTAS DA CARTEIRA" in msg
    assert "não é recomendação de investimento" in msg


def test_mensagem_com_ia_traz_indicadores_e_conclusao(snapshot_exemplo, ia_exemplo):
    msg = report.telegram(snapshot_exemplo, ia_exemplo, fundamentos(snapshot_exemplo, ia_exemplo))

    assert "P/VP médio <b>0,98</b>" in msg
    assert "Renda estimada" in msg
    assert "RISCOS PRIORIZADOS" in msg
    assert "FATOS RECENTES" in msg
    assert "CONCLUSÃO" in msg


def test_escapa_html_do_conteudo(snapshot_exemplo, ia_exemplo):
    ia = {**ia_exemplo, "resumo": "Risco <alto> & relevante"}
    msg = report.telegram(snapshot_exemplo, ia)

    assert "Risco &lt;alto&gt; &amp; relevante" in msg
    assert "<alto>" not in msg


def test_trunca_no_limite_do_telegram(snapshot_exemplo, ia_exemplo):
    ia = {**ia_exemplo, "resumo": "palavra " * 2000}
    msg = report.telegram(snapshot_exemplo, ia)

    assert len(msg) <= 4096
    assert msg.endswith("…")


def test_bloco_de_segmentos_so_com_mais_de_um(snapshot_exemplo, ia_exemplo):
    f = fundamentos(snapshot_exemplo, ia_exemplo)
    assert "POR SEGMENTO" not in report.telegram(snapshot_exemplo, ia_exemplo, f)

    f["por_segmento"].append(
        {"nome": "Logística", "valor": 5000.0, "peso_pct": 25.0, "ativos": ["HGLG11"], "quantidade": 1}
    )
    msg = report.telegram(snapshot_exemplo, ia_exemplo, f)
    assert "POR SEGMENTO" in msg
    assert "Logística: 25,0%" in msg

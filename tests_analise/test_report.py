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

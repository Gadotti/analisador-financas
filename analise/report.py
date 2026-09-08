"""Formatação do relatório para terminal e para o Telegram.

Estrutura, na ordem em que um relatório de análise é lido:
  1. Sumário executivo
  2. Indicadores-chave da carteira
  3. Alocação e concentrações
  4. Posições com fundamentos
  5. Ficha e comentário por ativo
  6. Riscos priorizados
  7. Fatos recentes e pontos de observação
  8. Contexto macro
"""

from __future__ import annotations

from datetime import datetime

from . import formato, portfolio
from .formato import LARGURA, data_br, moeda

SAUDE_ICONE = {"otima": "✅", "boa": "👍", "atencao": "⚠️", "alerta": "🚨"}
SAUDE_ROTULO = {"otima": "Ótima", "boa": "Boa", "atencao": "Atenção", "alerta": "Alerta"}
SEV_ICONE = {"info": "ℹ️", "atencao": "⚠️", "alerta": "🚨"}
OPP_ICONE = {
    "compra": "🟢",
    "monitorar": "👁",
    "setor": "📊",
    "macro": "🌐",
    "renda_fixa": "🏦",
    "rebalanceamento": "⚖️",
}
TIPO_ROTULO = {"fii": "FII", "acao": "Ação", "cdb": "CDB", "tesouro": "TD"}
CUPOM_ROTULO = {"mensal": "juros mensais", "semestral": "juros semestrais"}

# Teto de uma mensagem do Telegram, contado por ele em unidades UTF-16.
LIMITE_TELEGRAM = 4096
AVISO_CORTE = "<i>… relatório cortado no limite de tamanho do Telegram.</i>"


# ─────────────────────────────────────────────
# Terminal
# ─────────────────────────────────────────────

def _cupons(p: dict) -> str:
    """Linha extra de um título que paga juros no caminho, com o próximo cupom."""
    proximo = (
        f"próximo em {data_br(p['proximo_pagamento'])}"
        if p.get("proximo_pagamento") else "sem novos pagamentos"
    )
    return (
        f"         {CUPOM_ROTULO[p['pagamento_juros']]} · {p['pagamentos_realizados']} pagamento(s) · "
        f"{moeda(p['juros_recebidos_liquido'])} líquidos recebidos · {proximo}"
    )


def _nome_na_tabela(p: dict) -> str:
    """Coluna ATIVO de um título: o banco no CDB, o papel no Tesouro.

    O prefixo "Tesouro" sai porque a coluna do tipo já traz "TD"; o que
    identifica o papel é a família e o ano de vencimento.
    """
    if p["tipo"] == "cdb":
        return p["banco"]
    return p["descricao"].removeprefix("Tesouro ")


def _marcacao(p: dict) -> str:
    """Linha do título público: a taxa travada e quanto ele vale na curva.

    Só o Tesouro aparece aqui — o CDB não tem preço de revenda publicado, então
    para ele a curva já é o valor da posição, e repeti-la não diria nada.
    """
    origem = "informada" if p.get("taxa_origem") == "cadastro" else "do pregão da compra"
    return (
        f"         travado a {p['rotulo_taxa']} ({origem}) · "
        f"na curva {moeda(p['valor_na_curva'])} · "
        f"mercado de {data_br(p['cotacao_em'])}"
    )


def _linha_renda_fixa(p: dict) -> list[str]:
    """Detalhe abaixo da linha da posição: emissor, prazo e valor líquido."""
    situacao = "VENCIDO" if p["vencido"] else f"vence em {p['dias_para_vencer']} dias"
    linhas = [
        f"         {p['emissor']} · {data_br(p['data_vencimento'])} · {situacao}"
        f" · líquido estimado {moeda(p['valor_liquido'])}"
    ]
    if p.get("marcado_a_mercado"):
        linhas.append(_marcacao(p))
    if p["pagamento_juros"] != "vencimento":
        linhas.append(_cupons(p))
    if p.get("erro_cotacao"):
        linhas.append(f"         ⚠ {p['aviso']}")
    return linhas


def _emissores_rf(snapshot: dict) -> list[str]:
    """Exposição por banco emissor — o lado de renda fixa do recorte por emissor."""
    emissores = snapshot["emissores_renda_fixa"]
    if not emissores:
        return []

    linhas = ["", "  Por emissor de renda fixa (% da renda fixa)"]
    for e in emissores:
        marcador = "  ⚠ acima do FGC" if e["acima_do_fgc"] else ""
        cobertura = (
            f"{formato.pct(e['fgc_uso_pct'], 0, sinal=False)} do FGC"
            if e["fgc_limite"] else "garantia do Tesouro Nacional"
        )
        linhas.append(
            f"  {e['nome'][:28]:<28} {formato.pct(e['peso_pct'], 1, sinal=False):>6}"
            f"  {moeda(e['valor']):>15}  {cobertura}{marcador}"
        )
    return linhas


def _leitura_herdada(snapshot: dict, ia: dict | None) -> str:
    """Data da análise que produziu as fichas, ou "" quando é a desta execução.

    Uma execução sem IA herda a leitura da anterior (ver `runner._reaproveitar_ia`);
    sem esta marca o relatório apresentaria comentários antigos como se fossem
    de agora.
    """
    gerado_em = ((ia or {}).get("_meta") or {}).get("gerado_em") or ""
    if not gerado_em or gerado_em[:10] == snapshot["data"]:
        return ""
    return datetime.fromisoformat(gerado_em).strftime("%d/%m/%Y às %H:%M")


def texto(snapshot: dict, ia: dict | None = None, fundamentos: dict | None = None) -> str:
    borda = "═" * LARGURA
    t = snapshot["totais"]
    saude = snapshot["saude_carteira"]
    quando = datetime.fromisoformat(snapshot["gerado_em"]).strftime("%d/%m/%Y às %H:%M")

    out: list[str] = [
        borda,
        "  RELATÓRIO DE CARTEIRA".ljust(LARGURA - len(quando) - 2) + quando,
        borda,
    ]

    # ── 1. Sumário executivo ──
    if ia and ia.get("resumo"):
        out += ["", formato.quebrar(ia["resumo"], "  ")]

    # ── 2. Indicadores-chave ──
    out += formato.secao("Posição consolidada")
    out += [
        f"  Valor de mercado ........ {moeda(t['valor_atual'])}",
        f"  Custo de aquisição ...... {moeda(t['valor_investido'])}",
        f"  Resultado acumulado ..... {moeda(t['resultado'])}  ({formato.pct(t['resultado_pct'])}) {formato.marcador(t['resultado'])}",
    ]
    if t["resultado_dia"]:
        out.append(
            f"  Variação do dia ......... {moeda(t['resultado_dia'])} {formato.marcador(t['resultado_dia'])}"
        )
    out.append(
        f"  Saúde da carteira ....... {SAUDE_ICONE.get(saude, '')} {SAUDE_ROTULO.get(saude, saude)}"
        f"   ·   {len(snapshot['alertas'])} alerta(s)"
    )

    if fundamentos:
        m = fundamentos["metricas"]
        out += ["", "  INDICADORES DA RENDA VARIÁVEL"]
        if m["p_vp_medio"]:
            leitura = "desconto patrimonial" if m["p_vp_medio"] < 1 else "ágio sobre o patrimônio"
            out.append(
                f"  P/VP médio ponderado .... {formato.num(m['p_vp_medio'], 2)}  ({leitura})"
                f"   ·   cobertura {m['p_vp_cobertura']}"
            )
            out.append(
                f"     {m['com_desconto']} ativo(s) abaixo de 1,00 e {m['com_agio']} acima"
                + (f" · maior desconto: {m['maior_desconto']}" if m["maior_desconto"] else "")
                + (f" · maior ágio: {m['maior_agio']}" if m["maior_agio"] else "")
            )
        if m["dy_medio_pct"]:
            out.append(
                f"  DY médio ponderado ...... {formato.pct(m['dy_medio_pct'], 2, sinal=False)} a.a."
                f"   ·   cobertura {m['dy_cobertura']}"
            )
            out.append(
                f"  Renda estimada .......... {moeda(m['renda_mensal_estimada'])}/mês  "
                f"({moeda(m['renda_anual_estimada'])}/ano)"
            )
            if m["maior_dy"]:
                out.append(f"     maior yield: {m['maior_dy']} · menor: {m['menor_dy']}")

    # ── 3. Alocação ──
    out += formato.secao("Alocação")
    for classe in snapshot["classes"].values():
        barra = "█" * max(int(classe["peso_pct"] / 3), 1)
        out.append(
            f"  {classe['rotulo']:<15} {formato.pct(classe['peso_pct'], 1, sinal=False):>6}  {barra}"
        )
        out.append(
            f"           {moeda(classe['valor_atual'])}  ({formato.pct(classe['resultado_pct'], 1)})"
            f"  ·  {classe['posicoes']} ativo(s)"
        )

    if fundamentos:
        # O limite vale sobre a base do recorte — aqui, a renda variável.
        limite_conc = snapshot["limite_concentracao_pct"]
        for titulo, chave in (
            ("Por classificação", "por_classificacao"),
            ("Por segmento", "por_segmento"),
            ("Por gestora", "por_gestora"),
        ):
            grupos = fundamentos[chave]
            if len(grupos) <= 1 and chave != "por_segmento":
                continue
            out += ["", f"  {titulo} (% da renda variável)"]
            for g in grupos:
                marcador = "  ⚠" if g["peso_pct"] > limite_conc else "   "
                out.append(
                    f"  {g['nome'][:28]:<28} {formato.pct(g['peso_pct'], 1, sinal=False):>6}"
                    f"  {moeda(g['valor']):>15}  {', '.join(g['ativos'])}{marcador}".rstrip()
                )

        nao_coberto = fundamentos["nao_coberto"]
        if nao_coberto["valor"]:
            out.append(
                f"  {'Sem ficha (renda variável)':<28} "
                f"{formato.pct(nao_coberto['peso_pct'], 1, sinal=False):>6}"
                f"  {moeda(nao_coberto['valor']):>15}"
            )

    out += _emissores_rf(snapshot)

    # ── 4. Posições ──
    out += formato.secao("Posições")
    cabecalho = (
        f"  {'':>6} {'ATIVO':<18} {'SEGMENTO':<21} {'P/VP':>6} {'DY 12M':>8} "
        f"{'VALOR':>14} {'RESULT.':>9} {'PESO':>6}"
    )
    out += [cabecalho, "  " + "·" * (LARGURA - 2)]

    fichas = {f["ticker"]: f for f in (fundamentos["fichas"] if fundamentos else [])}

    for p in snapshot["posicoes"]:
        rotulo = TIPO_ROTULO[p["tipo"]]
        ficha = fichas.get(p.get("ticker", ""))

        if p["tipo"] in portfolio.TIPOS_RENDA_FIXA:
            nome = _nome_na_tabela(p)[:18]
            segmento = p["rotulo_taxa"][:21]
            pvp = dy = "—"
        else:
            nome = p["ticker"]
            segmento = (ficha["segmento"][:21] if ficha else "—")
            pvp = formato.num(ficha["p_vp"], 2) if ficha and ficha.get("p_vp") else "—"
            dy = formato.pct(ficha["dy_12m_pct"], 1, sinal=False) if ficha and ficha.get("dy_12m_pct") else "—"

        out.append(
            f"  [{rotulo:>4}] {nome:<18} {segmento:<21} {pvp:>6} {dy:>8} "
            f"{moeda(p['valor_atual']):>14} {formato.pct(p['resultado_pct'], 1):>9} "
            f"{formato.pct(p['peso_pct'], 1, sinal=False):>6}"
        )

        if p["tipo"] in portfolio.TIPOS_RENDA_FIXA:
            out += _linha_renda_fixa(p)
        else:
            preco = moeda(p["preco_atual"]) if p["preco_atual"] else "sem cotação"
            out.append(f"         {p['quantidade']:g} × {preco} · PM {moeda(p['preco_medio'])}")

    # ── 5. Ficha por ativo ──
    if fundamentos:
        out += formato.secao("Análise por ativo")
        for f in fundamentos["fichas"]:
            out.append(f"  ▸ {f['ticker']} — {f.get('nome', '')}")
            atributos = [
                f"{f['classificacao_rotulo']}",
                f"{f.get('segmento', '—')}",
                f"gestão {f.get('gestora')}" if f.get("gestora") else None,
                f"PL {f.get('patrimonio')}" if f.get("patrimonio") else None,
                f"P/VP {formato.num(f.get('p_vp'), 2)}" if f.get("p_vp") else None,
                f"DY {formato.pct(f.get('dy_12m_pct'), 1, sinal=False)}" if f.get("dy_12m_pct") else None,
                f"vacância {formato.pct(f.get('vacancia_pct'), 1, sinal=False)}" if f.get("vacancia_pct") else None,
            ]
            out.append(formato.quebrar(" · ".join(a for a in atributos if a), "    "))
            out.append("")
            out.append(formato.quebrar(f.get("comentario", ""), "    "))
            if f.get("risco"):
                out.append(formato.quebrar(f"Risco: {f['risco']}", "    "))
            if f.get("fonte"):
                out.append(f"    fonte: {f['fonte']}")
            out.append("")

    # ── 6. Leitura da carteira ──
    if ia and ia.get("carteira"):
        c = ia["carteira"]
        out += formato.secao("Leitura da carteira")
        for titulo, chave in (
            ("Diversificação", "diversificacao"),
            ("Concentração setorial", "concentracao_setorial"),
            ("Concentração de gestor / emissor", "concentracao_gestor"),
            ("Valuation", "valuation"),
            ("Geração de renda", "renda"),
        ):
            if c.get(chave):
                out.append(f"  {titulo}")
                out.append(formato.quebrar(c[chave], "    "))
                out.append("")
        if c.get("conclusao"):
            out.append("  Conclusão")
            out.append(formato.quebrar(c["conclusao"], "    "))

    # ── 7. Riscos ──
    riscos_ia = (ia or {}).get("riscos") or []
    if snapshot["alertas"] or riscos_ia:
        out += formato.secao("Riscos e alertas")

        if snapshot["alertas"]:
            out.append("  Detectados pelo cálculo da carteira")
            for a in snapshot["alertas"]:
                out.append(f"  {SEV_ICONE.get(a['severidade'], '•')} {a['titulo']}")
                out.append(formato.quebrar(a["descricao"], "     "))
            out.append("")

        if riscos_ia:
            out.append("  Levantados na análise, por ordem de relevância")
            for i, r in enumerate(riscos_ia, 1):
                ativos = f"  [{', '.join(r['ativos'])}]" if r.get("ativos") else ""
                out.append(f"  {i}. {SEV_ICONE.get(r.get('severidade'), '•')} {r['titulo']}{ativos}")
                out.append(formato.quebrar(r["descricao"], "     "))

    # ── 8. Fatos e observações ──
    if ia and ia.get("fatos"):
        out += formato.secao("Fatos recentes")
        for f in ia["fatos"]:
            out.append(f"  {SEV_ICONE.get(f.get('severidade'), '•')} [{f['ativo']}] {f['titulo']}")
            out.append(formato.quebrar(f["descricao"], "     "))
            if f.get("fonte"):
                out.append(f"     fonte: {f['fonte']}")
            out.append("")

    if ia and ia.get("oportunidades"):
        out += formato.secao("Pontos de observação")
        for o in ia["oportunidades"]:
            ativos = f"  ({', '.join(o['ativos'])})" if o.get("ativos") else ""
            out.append(f"  {OPP_ICONE.get(o.get('tipo'), '•')} {o['titulo']}{ativos}")
            out.append(formato.quebrar(o["descricao"], "     "))
            out.append("")

    # ── 9. Contexto macro ──
    macro = snapshot["macro"]
    out += formato.secao("Contexto de mercado")
    out.append(
        f"  CDI {formato.num(macro['cdi_anual_pct']['valor'])}% a.a.   ·   "
        f"Selic {formato.num(macro['selic_meta_pct']['valor'])}% a.a.   ·   "
        f"IPCA 12m {formato.num(macro['ipca_12m_pct'].get('valor'))}%"
    )
    ibov = macro["indices"].get("ibovespa")
    if ibov:
        pontos = f"{ibov['valor']:,.0f}".replace(",", ".")
        out.append(f"  Ibovespa {pontos} pts ({formato.pct(ibov['variacao_dia_pct'])} no dia)")

    if ia and ia.get("contexto_mercado"):
        out += ["", formato.quebrar(ia["contexto_mercado"], "  ")]

    # ── Rodapé ──
    if ia and ia.get("_meta"):
        m = ia["_meta"]
        buscas = f" · {m['buscas_web']} buscas web" if m.get("buscas_web") else ""
        out += ["", f"  Análise gerada por {m.get('modelo', '?')} (effort {m.get('effort')}){buscas}."]
        herdada = _leitura_herdada(snapshot, ia)
        if herdada:
            out.append(
                f"  Leitura herdada da análise de {herdada} — esta execução não chamou a IA."
            )

    out += [
        "",
        borda,
        "  CDB é estimado na curva; o Tesouro usa o preço de revenda do último pregão.",
        "  Indicadores de mercado levantados por IA — confira antes de decidir.",
        "  Este material é informativo e não constitui recomendação de investimento.",
        borda,
        "",
    ]
    return "\n".join(out)


# ─────────────────────────────────────────────
# Telegram (HTML)
# ─────────────────────────────────────────────

def _unidades_utf16(texto: str) -> int:
    """Comprimento como o Telegram conta: unidades UTF-16, não code points.

    Cada emoji fora do BMP vale 2 — medir em caracteres subestima o tamanho e
    o relatório, cheio de ícones, estouraria o limite mesmo parecendo caber.
    """
    return len(texto.encode("utf-16-le")) // 2


def _juntar_no_limite(
    linhas: list[str], rodape: list[str], limite: int = LIMITE_TELEGRAM
) -> str:
    """Junta corpo e rodapé sem passar do limite, descartando linhas do corpo.

    O corte é por linha inteira porque cada linha fecha as próprias tags:
    cortar no meio deixaria um `<b>` ou `<i>` aberto (ou uma entidade `&amp;`
    partida) e a API devolveria 400 — "can't parse entities". O rodapé é sempre
    mantido: é onde vai o aviso de que o material não é recomendação.
    """
    inteiro = linhas + rodape
    if _unidades_utf16("\n".join(inteiro)) <= limite:
        return "\n".join(inteiro)

    teto = limite - _unidades_utf16("\n".join([AVISO_CORTE] + rodape)) - 2
    mantidas: list[str] = []
    total = 0
    for linha in linhas:
        custo = _unidades_utf16(linha) + 1
        if total + custo > teto:
            break
        mantidas.append(linha)
        total += custo
    return "\n".join(mantidas + ["", AVISO_CORTE] + rodape)


def telegram(snapshot: dict, ia: dict | None = None, fundamentos: dict | None = None) -> str:
    t = snapshot["totais"]
    saude = snapshot["saude_carteira"]
    quando = datetime.fromisoformat(snapshot["gerado_em"]).strftime("%d/%m/%Y — %H:%M")

    linhas = [
        "📊 <b>Relatório de Carteira</b>",
        f"📅 {quando}",
        "",
        f"💰 <b>{moeda(t['valor_atual'])}</b>",
        f"{formato.marcador(t['resultado'])} {moeda(t['resultado'])} ({formato.pct(t['resultado_pct'])}) acumulado",
    ]
    if t["resultado_dia"]:
        linhas.append(f"{formato.marcador(t['resultado_dia'])} {moeda(t['resultado_dia'])} no dia")
    linhas += ["", f"{SAUDE_ICONE.get(saude, '')} <b>Saúde: {SAUDE_ROTULO.get(saude, saude)}</b>"]

    if ia and ia.get("resumo"):
        linhas += ["", f"<i>{formato.escapar_html(ia['resumo'])}</i>"]

    if fundamentos:
        m = fundamentos["metricas"]
        indicadores = []
        if m["p_vp_medio"]:
            indicadores.append(f"P/VP médio <b>{formato.num(m['p_vp_medio'], 2)}</b>")
        if m["dy_medio_pct"]:
            indicadores.append(f"DY médio <b>{formato.pct(m['dy_medio_pct'], 1, sinal=False)}</b>")
        if indicadores:
            linhas += ["", "━━━━━━━━━━━━━━━━", "📐 <b>INDICADORES</b>", " · ".join(indicadores)]
        if m["renda_mensal_estimada"]:
            linhas.append(f"Renda estimada: <b>{moeda(m['renda_mensal_estimada'])}/mês</b>")

    linhas += ["", "━━━━━━━━━━━━━━━━", "🗂 <b>ALOCAÇÃO</b>"]
    for classe in snapshot["classes"].values():
        linhas.append(
            f"• {classe['rotulo']}: {formato.pct(classe['peso_pct'], 1, sinal=False)} — "
            f"{moeda(classe['valor_atual'])} ({formato.pct(classe['resultado_pct'], 1)})"
        )

    if fundamentos and len(fundamentos["por_segmento"]) > 1:
        linhas += ["", "🏢 <b>POR SEGMENTO</b> <i>(% da renda variável)</i>"]
        for g in fundamentos["por_segmento"][:5]:
            linhas.append(
                f"• {formato.escapar_html(g['nome'])}: {formato.pct(g['peso_pct'], 1, sinal=False)} "
                f"({formato.escapar_html(', '.join(g['ativos']))})"
            )

    if snapshot["alertas"]:
        linhas += ["", "━━━━━━━━━━━━━━━━", "🔔 <b>ALERTAS DA CARTEIRA</b>"]
        for a in snapshot["alertas"]:
            linhas.append(f"\n{SEV_ICONE.get(a['severidade'], '•')} <b>{formato.escapar_html(a['titulo'])}</b>")
            linhas.append(f"<i>{formato.escapar_html(a['descricao'])}</i>")

    if ia and ia.get("riscos"):
        linhas += ["", "━━━━━━━━━━━━━━━━", "⚠️ <b>RISCOS PRIORIZADOS</b>"]
        for i, r in enumerate(ia["riscos"][:4], 1):
            ativos = f" ({formato.escapar_html(', '.join(r['ativos']))})" if r.get("ativos") else ""
            linhas.append(f"\n{i}. <b>{formato.escapar_html(r['titulo'])}</b>{ativos}")
            linhas.append(f"<i>{formato.escapar_html(r['descricao'])}</i>")

    if ia and ia.get("fatos"):
        linhas += ["", "━━━━━━━━━━━━━━━━", "📋 <b>FATOS RECENTES</b>"]
        for f in ia["fatos"][:4]:
            icone = SEV_ICONE.get(f.get("severidade"), "ℹ️")
            linhas.append(f"\n{icone} <b>[{formato.escapar_html(f['ativo'])}]</b> {formato.escapar_html(f['titulo'])}")
            linhas.append(f"<i>{formato.escapar_html(f['descricao'])}</i>")

    if ia and (ia.get("carteira") or {}).get("conclusao"):
        linhas += ["", "━━━━━━━━━━━━━━━━", "🎯 <b>CONCLUSÃO</b>", formato.escapar_html(ia["carteira"]["conclusao"])]

    herdada = _leitura_herdada(snapshot, ia)
    if herdada:
        linhas += ["", f"<i>🕓 Leitura herdada da análise de {herdada} — "
                       "esta execução não chamou a IA.</i>"]

    rodape = [
        "",
        "<i>⚠️ Valores de renda fixa são estimativas e indicadores foram levantados por IA. "
        "Material informativo, não é recomendação de investimento.</i>",
    ]

    return _juntar_no_limite(linhas, rodape)

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

import textwrap
from datetime import datetime

from .analysis import data_br, moeda

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
TIPO_ROTULO = {"fii": "FII", "acao": "Ação", "cdb": "CDB"}

LARGURA = 78


# ─────────────────────────────────────────────
# Formatação de números
# ─────────────────────────────────────────────

def _num(valor, casas: int = 2) -> str:
    """Número no formato brasileiro, ou travessão quando indisponível."""
    if valor is None:
        return "—"
    return f"{valor:.{casas}f}".replace(".", ",")


def _pct(valor, casas: int = 2, *, sinal: bool = True) -> str:
    """Percentual no formato brasileiro."""
    if valor is None:
        return "—"
    texto = f"{valor:{'+' if sinal else ''}.{casas}f}".replace(".", ",")
    return f"{texto}%"


def _sinal(valor: float) -> str:
    return "🟢" if valor > 0 else ("🔴" if valor < 0 else "⚪")


def _quebrar(texto: str, recuo: str = "      ", largura: int = LARGURA) -> str:
    """Quebra um parágrafo respeitando a largura do relatório."""
    return textwrap.fill(
        texto or "",
        width=largura,
        initial_indent=recuo,
        subsequent_indent=recuo,
    )


def _secao(titulo: str) -> list[str]:
    return ["", "─" * LARGURA, f"  {titulo.upper()}", "─" * LARGURA, ""]


# ─────────────────────────────────────────────
# Terminal
# ─────────────────────────────────────────────

def _emissores_rf(snapshot: dict) -> list[str]:
    """Exposição por banco emissor — o lado de renda fixa do recorte por emissor."""
    emissores = snapshot["emissores_renda_fixa"]
    if not emissores:
        return []

    linhas = ["", "  Por emissor de renda fixa (% da carteira)"]
    for e in emissores:
        marcador = "  ⚠ acima do FGC" if e["acima_do_fgc"] else ""
        linhas.append(
            f"  {e['nome'][:28]:<28} {_pct(e['peso_pct'], 1, sinal=False):>6}"
            f"  {moeda(e['valor']):>15}  {_pct(e['fgc_uso_pct'], 0, sinal=False)} do FGC"
            f"{marcador}"
        )
    return linhas


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
        out += ["", _quebrar(ia["resumo"], "  ")]

    # ── 2. Indicadores-chave ──
    out += _secao("Posição consolidada")
    out += [
        f"  Valor de mercado ........ {moeda(t['valor_atual'])}",
        f"  Custo de aquisição ...... {moeda(t['valor_investido'])}",
        f"  Resultado acumulado ..... {moeda(t['resultado'])}  ({_pct(t['resultado_pct'])}) {_sinal(t['resultado'])}",
    ]
    if t["resultado_dia"]:
        out.append(
            f"  Variação do dia ......... {moeda(t['resultado_dia'])} {_sinal(t['resultado_dia'])}"
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
                f"  P/VP médio ponderado .... {_num(m['p_vp_medio'], 2)}  ({leitura})"
                f"   ·   cobertura {m['p_vp_cobertura']}"
            )
            out.append(
                f"     {m['com_desconto']} ativo(s) abaixo de 1,00 e {m['com_agio']} acima"
                + (f" · maior desconto: {m['maior_desconto']}" if m["maior_desconto"] else "")
                + (f" · maior ágio: {m['maior_agio']}" if m["maior_agio"] else "")
            )
        if m["dy_medio_pct"]:
            out.append(
                f"  DY médio ponderado ...... {_pct(m['dy_medio_pct'], 2, sinal=False)} a.a."
                f"   ·   cobertura {m['dy_cobertura']}"
            )
            out.append(
                f"  Renda estimada .......... {moeda(m['renda_mensal_estimada'])}/mês  "
                f"({moeda(m['renda_anual_estimada'])}/ano)"
            )
            if m["maior_dy"]:
                out.append(f"     maior yield: {m['maior_dy']} · menor: {m['menor_dy']}")

    # ── 3. Alocação ──
    out += _secao("Alocação")
    for classe in snapshot["classes"].values():
        barra = "█" * max(int(classe["peso_pct"] / 3), 1)
        out.append(
            f"  {classe['rotulo']:<8} {_pct(classe['peso_pct'], 1, sinal=False):>6}  {barra}"
        )
        out.append(
            f"           {moeda(classe['valor_atual'])}  ({_pct(classe['resultado_pct'], 1)})"
            f"  ·  {classe['posicoes']} ativo(s)"
        )

    if fundamentos:
        limite_conc = snapshot["limite_concentracao_pct"]
        for titulo, chave in (
            ("Por classificação", "por_classificacao"),
            ("Por segmento", "por_segmento"),
            ("Por gestora", "por_gestora"),
        ):
            grupos = fundamentos[chave]
            if len(grupos) <= 1 and chave != "por_segmento":
                continue
            out += ["", f"  {titulo} (% da carteira)"]
            for g in grupos:
                marcador = "  ⚠" if g["peso_pct"] > limite_conc else "   "
                out.append(
                    f"  {g['nome'][:28]:<28} {_pct(g['peso_pct'], 1, sinal=False):>6}"
                    f"  {moeda(g['valor']):>15}  {', '.join(g['ativos'])}{marcador}".rstrip()
                )

        nao_coberto = fundamentos["nao_coberto"]
        if nao_coberto["valor"]:
            out.append(
                f"  {'Sem ficha (renda fixa)':<28} "
                f"{_pct(nao_coberto['peso_pct'], 1, sinal=False):>6}"
                f"  {moeda(nao_coberto['valor']):>15}"
            )

    out += _emissores_rf(snapshot)

    # ── 4. Posições ──
    out += _secao("Posições")
    cabecalho = (
        f"  {'':>6} {'ATIVO':<12} {'SEGMENTO':<19} {'P/VP':>6} {'DY 12M':>8} "
        f"{'VALOR':>14} {'RESULT.':>9} {'PESO':>6}"
    )
    out += [cabecalho, "  " + "·" * (LARGURA - 2)]

    fichas = {f["ticker"]: f for f in (fundamentos["fichas"] if fundamentos else [])}

    for p in snapshot["posicoes"]:
        rotulo = TIPO_ROTULO[p["tipo"]]
        ficha = fichas.get(p.get("ticker", ""))

        if p["tipo"] == "cdb":
            nome = p["banco"][:12]
            segmento = f"CDB {p['rotulo_taxa']}"[:19]
            pvp = dy = "—"
        else:
            nome = p["ticker"]
            segmento = (ficha["segmento"][:19] if ficha else "—")
            pvp = _num(ficha["p_vp"], 2) if ficha and ficha.get("p_vp") else "—"
            dy = _pct(ficha["dy_12m_pct"], 1, sinal=False) if ficha and ficha.get("dy_12m_pct") else "—"

        out.append(
            f"  [{rotulo:>4}] {nome:<12} {segmento:<19} {pvp:>6} {dy:>8} "
            f"{moeda(p['valor_atual']):>14} {_pct(p['resultado_pct'], 1):>9} "
            f"{_pct(p['peso_pct'], 1, sinal=False):>6}"
        )

        if p["tipo"] == "cdb":
            situacao = "VENCIDO" if p["vencido"] else f"vence em {p['dias_para_vencer']} dias"
            out.append(
                f"         {p['banco']} · {data_br(p['data_vencimento'])} · {situacao}"
                f" · líquido estimado {moeda(p['valor_liquido'])}"
            )
        else:
            preco = moeda(p["preco_atual"]) if p["preco_atual"] else "sem cotação"
            out.append(f"         {p['quantidade']:g} × {preco} · PM {moeda(p['preco_medio'])}")

    # ── 5. Ficha por ativo ──
    if fundamentos:
        out += _secao("Análise por ativo")
        for f in fundamentos["fichas"]:
            out.append(f"  ▸ {f['ticker']} — {f.get('nome', '')}")
            atributos = [
                f"{f['classificacao_rotulo']}",
                f"{f.get('segmento', '—')}",
                f"gestão {f.get('gestora')}" if f.get("gestora") else None,
                f"PL {f.get('patrimonio')}" if f.get("patrimonio") else None,
                f"P/VP {_num(f.get('p_vp'), 2)}" if f.get("p_vp") else None,
                f"DY {_pct(f.get('dy_12m_pct'), 1, sinal=False)}" if f.get("dy_12m_pct") else None,
                f"vacância {_pct(f.get('vacancia_pct'), 1, sinal=False)}" if f.get("vacancia_pct") else None,
            ]
            out.append(_quebrar(" · ".join(a for a in atributos if a), "    "))
            out.append("")
            out.append(_quebrar(f.get("comentario", ""), "    "))
            if f.get("risco"):
                out.append(_quebrar(f"Risco: {f['risco']}", "    "))
            if f.get("fonte"):
                out.append(f"    fonte: {f['fonte']}")
            out.append("")

    # ── 6. Leitura da carteira ──
    if ia and ia.get("carteira"):
        c = ia["carteira"]
        out += _secao("Leitura da carteira")
        for titulo, chave in (
            ("Diversificação", "diversificacao"),
            ("Concentração setorial", "concentracao_setorial"),
            ("Concentração de gestor / emissor", "concentracao_gestor"),
            ("Valuation", "valuation"),
            ("Geração de renda", "renda"),
        ):
            if c.get(chave):
                out.append(f"  {titulo}")
                out.append(_quebrar(c[chave], "    "))
                out.append("")
        if c.get("conclusao"):
            out.append("  Conclusão")
            out.append(_quebrar(c["conclusao"], "    "))

    # ── 7. Riscos ──
    riscos_ia = (ia or {}).get("riscos") or []
    if snapshot["alertas"] or riscos_ia:
        out += _secao("Riscos e alertas")

        if snapshot["alertas"]:
            out.append("  Detectados pelo cálculo da carteira")
            for a in snapshot["alertas"]:
                out.append(f"  {SEV_ICONE.get(a['severidade'], '•')} {a['titulo']}")
                out.append(_quebrar(a["descricao"], "     "))
            out.append("")

        if riscos_ia:
            out.append("  Levantados na análise, por ordem de relevância")
            for i, r in enumerate(riscos_ia, 1):
                ativos = f"  [{', '.join(r['ativos'])}]" if r.get("ativos") else ""
                out.append(f"  {i}. {SEV_ICONE.get(r.get('severidade'), '•')} {r['titulo']}{ativos}")
                out.append(_quebrar(r["descricao"], "     "))

    # ── 8. Fatos e observações ──
    if ia and ia.get("fatos"):
        out += _secao("Fatos recentes")
        for f in ia["fatos"]:
            out.append(f"  {SEV_ICONE.get(f.get('severidade'), '•')} [{f['ativo']}] {f['titulo']}")
            out.append(_quebrar(f["descricao"], "     "))
            if f.get("fonte"):
                out.append(f"     fonte: {f['fonte']}")
            out.append("")

    if ia and ia.get("oportunidades"):
        out += _secao("Pontos de observação")
        for o in ia["oportunidades"]:
            ativos = f"  ({', '.join(o['ativos'])})" if o.get("ativos") else ""
            out.append(f"  {OPP_ICONE.get(o.get('tipo'), '•')} {o['titulo']}{ativos}")
            out.append(_quebrar(o["descricao"], "     "))
            out.append("")

    # ── 9. Contexto macro ──
    macro = snapshot["macro"]
    out += _secao("Contexto de mercado")
    out.append(
        f"  CDI {_num(macro['cdi_anual_pct']['valor'])}% a.a.   ·   "
        f"Selic {_num(macro['selic_meta_pct']['valor'])}% a.a.   ·   "
        f"IPCA 12m {_num(macro['ipca_12m_pct'].get('valor'))}%"
    )
    ibov = macro["indices"].get("ibovespa")
    if ibov:
        pontos = f"{ibov['valor']:,.0f}".replace(",", ".")
        out.append(f"  Ibovespa {pontos} pts ({_pct(ibov['variacao_dia_pct'])} no dia)")

    if ia and ia.get("contexto_mercado"):
        out += ["", _quebrar(ia["contexto_mercado"], "  ")]

    # ── Rodapé ──
    if ia and ia.get("_meta"):
        m = ia["_meta"]
        buscas = f" · {m['buscas_web']} buscas web" if m.get("buscas_web") else ""
        out += ["", f"  Análise gerada por {m.get('modelo', '?')} (effort {m.get('effort')}){buscas}."]

    out += [
        "",
        borda,
        "  Valores de CDB são estimativas; o extrato do banco é a fonte oficial.",
        "  Indicadores de mercado levantados por IA — confira antes de decidir.",
        "  Este material é informativo e não constitui recomendação de investimento.",
        borda,
        "",
    ]
    return "\n".join(out)


# ─────────────────────────────────────────────
# Telegram (HTML)
# ─────────────────────────────────────────────

def _esc(txt) -> str:
    return str(txt or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def telegram(snapshot: dict, ia: dict | None = None, fundamentos: dict | None = None) -> str:
    t = snapshot["totais"]
    saude = snapshot["saude_carteira"]
    quando = datetime.fromisoformat(snapshot["gerado_em"]).strftime("%d/%m/%Y — %H:%M")

    linhas = [
        "📊 <b>Relatório de Carteira</b>",
        f"📅 {quando}",
        "",
        f"💰 <b>{moeda(t['valor_atual'])}</b>",
        f"{_sinal(t['resultado'])} {moeda(t['resultado'])} ({_pct(t['resultado_pct'])}) acumulado",
    ]
    if t["resultado_dia"]:
        linhas.append(f"{_sinal(t['resultado_dia'])} {moeda(t['resultado_dia'])} no dia")
    linhas += ["", f"{SAUDE_ICONE.get(saude, '')} <b>Saúde: {SAUDE_ROTULO.get(saude, saude)}</b>"]

    if ia and ia.get("resumo"):
        linhas += ["", f"<i>{_esc(ia['resumo'])}</i>"]

    if fundamentos:
        m = fundamentos["metricas"]
        indicadores = []
        if m["p_vp_medio"]:
            indicadores.append(f"P/VP médio <b>{_num(m['p_vp_medio'], 2)}</b>")
        if m["dy_medio_pct"]:
            indicadores.append(f"DY médio <b>{_pct(m['dy_medio_pct'], 1, sinal=False)}</b>")
        if indicadores:
            linhas += ["", "━━━━━━━━━━━━━━━━", "📐 <b>INDICADORES</b>", " · ".join(indicadores)]
        if m["renda_mensal_estimada"]:
            linhas.append(f"Renda estimada: <b>{moeda(m['renda_mensal_estimada'])}/mês</b>")

    linhas += ["", "━━━━━━━━━━━━━━━━", "🗂 <b>ALOCAÇÃO</b>"]
    for classe in snapshot["classes"].values():
        linhas.append(
            f"• {classe['rotulo']}: {_pct(classe['peso_pct'], 1, sinal=False)} — "
            f"{moeda(classe['valor_atual'])} ({_pct(classe['resultado_pct'], 1)})"
        )

    if fundamentos and len(fundamentos["por_segmento"]) > 1:
        linhas += ["", "🏢 <b>POR SEGMENTO</b>"]
        for g in fundamentos["por_segmento"][:5]:
            linhas.append(
                f"• {_esc(g['nome'])}: {_pct(g['peso_pct'], 1, sinal=False)} "
                f"({_esc(', '.join(g['ativos']))})"
            )

    if snapshot["alertas"]:
        linhas += ["", "━━━━━━━━━━━━━━━━", "🔔 <b>ALERTAS DA CARTEIRA</b>"]
        for a in snapshot["alertas"]:
            linhas.append(f"\n{SEV_ICONE.get(a['severidade'], '•')} <b>{_esc(a['titulo'])}</b>")
            linhas.append(f"<i>{_esc(a['descricao'])}</i>")

    if ia and ia.get("riscos"):
        linhas += ["", "━━━━━━━━━━━━━━━━", "⚠️ <b>RISCOS PRIORIZADOS</b>"]
        for i, r in enumerate(ia["riscos"][:4], 1):
            ativos = f" ({_esc(', '.join(r['ativos']))})" if r.get("ativos") else ""
            linhas.append(f"\n{i}. <b>{_esc(r['titulo'])}</b>{ativos}")
            linhas.append(f"<i>{_esc(r['descricao'])}</i>")

    if ia and ia.get("fatos"):
        linhas += ["", "━━━━━━━━━━━━━━━━", "📋 <b>FATOS RECENTES</b>"]
        for f in ia["fatos"][:4]:
            icone = SEV_ICONE.get(f.get("severidade"), "ℹ️")
            linhas.append(f"\n{icone} <b>[{_esc(f['ativo'])}]</b> {_esc(f['titulo'])}")
            linhas.append(f"<i>{_esc(f['descricao'])}</i>")

    if ia and (ia.get("carteira") or {}).get("conclusao"):
        linhas += ["", "━━━━━━━━━━━━━━━━", "🎯 <b>CONCLUSÃO</b>", _esc(ia["carteira"]["conclusao"])]

    linhas += [
        "",
        "<i>⚠️ Valores de CDB são estimativas e indicadores foram levantados por IA. "
        "Material informativo, não é recomendação de investimento.</i>",
    ]

    mensagem = "\n".join(linhas)
    # O Telegram limita mensagens a 4096 caracteres.
    return mensagem[:4090] + "…" if len(mensagem) > 4096 else mensagem

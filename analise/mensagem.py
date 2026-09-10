"""Mensagens do Telegram: o relatório inteiro e a mensagem curta do dia.

São dois formatos com invariantes iguais e propósitos opostos:

- `telegram` é o relatório completo, enviado sob demanda (`--completo`);
- `telegram_resumo` é o envio de cada dia, e traz **só** o que a seleção de
  `analise.relevancia` decidiu que merece ser dito hoje.

O relatório de terminal mora em `analise.report`; o que os dois compartilham
(ícones, rótulos e a marca da leitura herdada) está em `analise.formato`.

**O HTML é restrito e o corte é por linha.** O Telegram recusa a mensagem
inteira com 400 se houver tag aberta, entidade partida ou mais de 4096
caracteres. Por isso todo texto vindo da IA ou do cadastro passa por
`formato.escapar_html` e **cada linha fecha as próprias tags**: é essa
invariante que permite a `_juntar_no_limite` descartar linhas inteiras. Nunca
volte a cortar a string no meio (`mensagem[:4090]`) — um `<i>` aberto derruba
o envio.
"""

from __future__ import annotations

from datetime import datetime

from . import formato, portfolio
from .formato import (
    SAUDE_ICONE,
    SAUDE_ROTULO,
    SEV_ICONE,
    data_br,
    leitura_herdada,
    moeda,
)

# Teto de uma mensagem do Telegram, contado por ele em unidades UTF-16.
LIMITE_TELEGRAM = 4096
AVISO_CORTE = "<i>… relatório cortado no limite de tamanho do Telegram.</i>"

# Ícone por tipo de ponto de observação da IA.
OPP_ICONE = {
    "compra": "🟢",
    "monitorar": "👁",
    "setor": "📊",
    "macro": "🌐",
    "renda_fixa": "🏦",
    "rebalanceamento": "⚖️",
}


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

    herdada = leitura_herdada(snapshot["data"], (ia or {}).get("_meta"))
    if herdada:
        linhas += ["", f"<i>🕓 Leitura herdada da análise de {herdada} — "
                       "esta execução não chamou a IA.</i>"]

    rodape = [
        "",
        "<i>⚠️ Valores de renda fixa são estimativas e indicadores foram levantados por IA. "
        "Material informativo, não é recomendação de investimento.</i>",
    ]

    return _juntar_no_limite(linhas, rodape)


# ─────────────────────────────────────────────
# Telegram — mensagem curta do dia
# ─────────────────────────────────────────────

RODAPE_RESUMO = [
    "",
    "<i>⚠️ Informativo, não é recomendação de investimento.</i>",
]


def _linha_estado(estado: dict) -> str:
    """A âncora da mensagem: valor, dia e acumulado numa linha só.

    O estado da carteira não é notícia — quem quer o detalhe abre a interface.
    Ele está aqui para dar escala ao que vem depois.
    """
    partes = [f"📊 <b>{moeda(estado['valor_atual'])}</b>"]
    if estado["variacao_dia_pct"] is not None:
        partes.append(f"{formato.pct(estado['variacao_dia_pct'])} no dia")
    partes.append(f"{formato.pct(estado['resultado_pct'])} acumulado")
    return " · ".join(partes)


def _linhas_item(item: dict) -> list[str]:
    """Um item selecionado: título com ícone e, quando houver, o detalhe.

    Cada linha fecha as próprias tags — é isso que permite a
    `_juntar_no_limite` descartar linhas inteiras sem partir o HTML.
    """
    linhas = ["", f"{item['icone']} <b>{formato.escapar_html(item['titulo'])}</b>"]
    if item.get("detalhe"):
        linhas.append(f"<i>{formato.escapar_html(item['detalhe'])}</i>")
    return linhas


def _linhas_semanal(semanal: dict) -> list[str]:
    """Fechamento do dia da semana escolhido: extremos e agenda do próximo mês."""
    linhas = ["", "━━━━━━━━━━━━━━━━", f"🗓 <b>Fechamento de {semanal['dia']}</b>"]

    for icone, chave in (("🥇", "melhor"), ("🔻", "pior")):
        ponta = semanal.get(chave)
        if ponta:
            linhas.append(
                f"{icone} {formato.escapar_html(ponta['descricao'])}: "
                f"{formato.pct(ponta['resultado_pct'], 1)} acumulado"
            )

    for evento in semanal["agenda"]:
        linhas.append(
            f"📅 {formato.escapar_html(evento['descricao'])} {evento['verbo']} em "
            f"{data_br(evento['data'])} · {moeda(evento['valor_liquido'])} líquidos"
        )
    return linhas


def telegram_resumo(selecao: dict) -> str:
    """Mensagem curta do dia, a partir da seleção de `analise.relevancia`.

    Só o estado e o rodapé são fixos; todo o resto entrou porque cruzou um
    limiar do cadastro. Num dia em que nada cruzou, a mensagem é a linha de
    estado e a contagem de alertas em curso — e é assim que se pretende.
    """
    linhas = [_linha_estado(selecao["estado"])]
    for item in selecao["itens"]:
        linhas += _linhas_item(item)
    linhas += _linhas_de_fecho(selecao)

    return _juntar_no_limite(linhas, RODAPE_RESUMO)


def _linhas_de_fecho(selecao: dict) -> list[str]:
    """O que vem depois dos itens: alertas em curso, semanal, resumo e herança."""
    linhas = []
    if selecao["alertas_em_curso"]:
        linhas += [
            "",
            f"⚠️ <i>{selecao['alertas_em_curso']} alerta(s) em curso — "
            "veja o detalhe na interface.</i>",
        ]
    if selecao.get("semanal"):
        linhas += _linhas_semanal(selecao["semanal"])
    if selecao.get("resumo_ia"):
        linhas += ["", f"💬 <i>{formato.escapar_html(selecao['resumo_ia'])}</i>"]

    herdada = leitura_herdada(selecao["data"], selecao.get("ia_meta"))
    if herdada:
        linhas += ["", f"<i>🕓 Leitura de IA herdada de {herdada}.</i>"]
    return linhas

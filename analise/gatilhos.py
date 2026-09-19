"""Quando cada bloco da mensagem curta fala, e o que ele diz.

Um bloco é uma função que recebe o contexto do dia e devolve zero ou mais
itens. Devolver lista vazia **é** o gatilho: o bloco simplesmente não tem nada
a dizer hoje. Não há um `gatilho()` separado do `montar()` porque seriam duas
funções para uma decisão só.

A tabela `BLOCOS` declara a ordem de leitura e o peso de cada bloco no corte
por orçamento. Um bloco novo é uma linha nova ali — nunca um `if` no meio do
montador. Quem junta, pontua, corta e monta a seleção é `analise.relevancia`;
quem formata é `analise.mensagem`. Aqui não se escreve HTML.

Nada neste módulo lê disco, rede ou histórico: os itens saem do snapshot desta
execução e dos limiares do cadastro. A exceção é `_macro`, que compara três
indicadores com a leitura anterior — ver `relevancia.macro_comparavel`.

Os blocos `alertas`, `riscos_ia` e `fatos_ia` recebem em `ctx["estado_envio"]`
o que já foi enviado (injetado por `relevancia`, nunca lido do disco aqui) e
filtram por ele **antes** do corte por `max` do próprio bloco — é o que faz um
achado que nunca coube no teto subir para a mensagem seguinte assim que o de
cima é marcado como enviado, em vez de ficar esquecido atrás dele para sempre.
Cada item carrega `chave_envio`, o hash do texto cru de origem
(`analise.estado_envio`, puro — sem I/O), usado depois para gravar o que saiu.
"""

from __future__ import annotations

from datetime import date

from . import estado_envio, formato, portfolio
from .formato import SEV_ICONE, moeda

# Indicadores macro comparados com a execução anterior, na ordem em que saem.
MACRO_COMPARADO = (
    ("selic_meta_pct", "Selic meta", "% a.a."),
    ("cdi_anual_pct", "CDI", "% a.a."),
    ("ipca_12m_pct", "IPCA 12m", "%"),
)

ORDEM_SEVERIDADE = {"info": 1, "atencao": 2, "alerta": 3}
PESO_SEVERIDADE = {"info": 1.0, "atencao": 2.0, "alerta": 3.0}

# Teto do comentário do ativo do dia — ver `_primeiras_frases`.
LIMITE_COMENTARIO = 220


# ─────────────────────────────────────────────
# Apoio
# ─────────────────────────────────────────────

def config_do_bloco(cfg: dict, chave: str) -> dict:
    """Configuração de um bloco, completada com os padrões que faltarem."""
    padrao = portfolio.TELEGRAM_PADRAO.get(chave) or {}
    return {**padrao, **(cfg.get(chave) or {})}


def dias_ate(iso: str | None, hoje: date) -> int | None:
    """Dias corridos de hoje até uma data ISO, ou None quando não há data."""
    alvo = portfolio.data_iso(iso)
    return (alvo - hoje).days if alvo else None


def variacao_carteira_pct(totais: dict) -> float | None:
    """Variação do dia da carteira em %, a partir do resultado do dia em reais."""
    resultado_dia = totais.get("resultado_dia") or 0.0
    abertura = totais["valor_atual"] - resultado_dia
    if not resultado_dia or not abertura:
        return None
    return resultado_dia / abertura * 100


def _passa_severidade(severidade: str | None, minima: str) -> bool:
    """A severidade do item atinge o piso configurado?"""
    return ORDEM_SEVERIDADE.get(severidade or "info", 1) >= ORDEM_SEVERIDADE.get(minima, 1)


def _item(
    bloco: str,
    icone: str,
    titulo: str,
    detalhe: str | None = None,
    *,
    severidade: str = "info",
    peso_pct: float = 0.0,
    chave_envio: str | None = None,
) -> dict:
    """Um item da mensagem, ainda sem HTML: quem formata é `analise.mensagem`.

    A relevância é multiplicativa de propósito — um fato grave sobre 2% da
    carteira não pesa como o mesmo fato sobre 30%. O peso do bloco entra
    depois, em `pontuar`, para que todos fiquem visíveis numa tabela só.

    `chave_envio` só existe nos blocos deduplicados (`estado_envio.BLOCOS`);
    nos demais fica `None` e `relevancia` não tenta filtrar por ele.
    """
    return {
        "bloco": bloco,
        "icone": icone,
        "titulo": titulo,
        "detalhe": detalhe,
        "severidade": severidade,
        "relevancia": PESO_SEVERIDADE.get(severidade, 1.0) * (1 + peso_pct / 100),
        "chave_envio": chave_envio,
    }


def pontuar(itens: list[dict], base: float) -> list[dict]:
    """Aplica o peso declarado do bloco à relevância dos itens que ele produziu."""
    for item in itens:
        item["relevancia"] = round(item["relevancia"] * base, 4)
    return itens


# ─────────────────────────────────────────────
# Variação do dia
# ─────────────────────────────────────────────

def _variacao_dia(ctx: dict) -> list[dict]:
    """A carteira andou mais que o limiar hoje?"""
    cfg = config_do_bloco(ctx["cfg"], "variacao_dia")
    totais = ctx["snapshot"]["totais"]
    pct = variacao_carteira_pct(totais)
    if pct is None or abs(pct) < float(cfg["limiar_pct"]):
        return []

    resultado_dia = totais["resultado_dia"]
    return [_item(
        "variacao_dia",
        formato.marcador(resultado_dia),
        f"Carteira {formato.pct(pct)} no dia",
        f"{moeda(resultado_dia)} em um dia.",
        severidade="atencao" if pct < 0 else "info",
    )]


# ─────────────────────────────────────────────
# Macro — a única comparação com o passado
# ─────────────────────────────────────────────

def valor_macro(macro: dict | None, chave: str) -> float | None:
    """Valor de um indicador macro, ou None quando a fonte falhou.

    `market._ultimo_valor` devolve um padrão embutido com `fonte: "padrao"`
    quando o Banco Central não responde. Comparar esse padrão com uma
    leitura real anunciaria uma mudança que não houve. Também usado por
    `runner._com_variacao_diaria`, que compara com o estado de ontem em vez
    da execução anterior.
    """
    bloco = (macro or {}).get(chave) or {}
    if bloco.get("fonte") == "padrao":
        return None
    valor = bloco.get("valor")
    return float(valor) if isinstance(valor, (int, float)) else None


def _macro(ctx: dict) -> list[dict]:
    """Indicadores macro que mudaram em relação ao estado anterior.

    Selic, CDI e IPCA mudam poucas vezes por ano, e a mudança reprecifica a
    carteira inteira — por isso a mudança **é** a notícia.
    """
    cfg = config_do_bloco(ctx["cfg"], "macro")
    limiar = float(cfg["limiar_pp"])
    itens = []
    for chave, rotulo, unidade in MACRO_COMPARADO:
        atual = valor_macro(ctx["snapshot"]["macro"], chave)
        antes = valor_macro(ctx["macro_anterior"], chave)
        if atual is None or antes is None or abs(atual - antes) < limiar:
            continue
        itens.append(_item_macro(rotulo, unidade, antes, atual))
    return itens


def _item_macro(rotulo: str, unidade: str, antes: float, atual: float) -> dict:
    """Uma linha de mudança de indicador, com o valor de onde ele veio."""
    delta = formato.num(abs(atual - antes), 2)
    return _item(
        "macro",
        "📈" if atual > antes else "📉",
        f"{rotulo} {'subiu' if atual > antes else 'caiu'} para "
        f"{formato.num(atual, 2)}{unidade}",
        f"Era {formato.num(antes, 2)}{unidade} na leitura anterior — "
        f"{delta} p.p. de diferença.",
        severidade="atencao",
    )


# ─────────────────────────────────────────────
# Posições em movimento
# ─────────────────────────────────────────────

def _movimento(ctx: dict) -> list[dict]:
    """Posições de renda variável que se moveram além do limiar hoje."""
    cfg = config_do_bloco(ctx["cfg"], "movimento")
    limiar = float(cfg["limiar_pct"])
    piso = float(cfg["peso_minimo_pct"])

    candidatas = [
        p for p in ctx["snapshot"]["posicoes"]
        if p.get("variacao_dia_pct") is not None
        and abs(p["variacao_dia_pct"]) >= limiar
        and p["peso_pct"] >= piso
    ]
    candidatas.sort(key=lambda p: abs(p["variacao_dia_pct"]), reverse=True)
    return [_item_movimento(p) for p in candidatas[: int(cfg["max"])]]


def _item_movimento(posicao: dict) -> dict:
    """Uma posição que se moveu: quanto andou, quanto vale e que peso tem."""
    variacao = posicao["variacao_dia_pct"]
    return _item(
        "movimento",
        "📉" if variacao < 0 else "📈",
        f"{posicao['descricao']} {formato.pct(variacao, 1)} no dia",
        f"{moeda(posicao['valor_atual'])} · "
        f"{formato.pct(posicao['peso_pct'], 1, sinal=False)} da carteira.",
        severidade="atencao" if variacao < 0 else "info",
        peso_pct=posicao["peso_pct"],
    )


# ─────────────────────────────────────────────
# Calendário de renda fixa — marcos, não janela
# ─────────────────────────────────────────────

def _calendario_rf(ctx: dict) -> list[dict]:
    """Cupom creditado hoje e marcos de vencimento ou de cupom à frente.

    O gatilho é o marco, não a janela: `dias_para_vencer in {30, 15, 7, 3, 1}`
    cita o vencimento cinco vezes na vida do título, em dias distintos, onde
    "faltam menos de 30 dias" o citaria trinta vezes seguidas.
    """
    cfg = config_do_bloco(ctx["cfg"], "calendario_rf")
    marcos = {int(d) for d in cfg["marcos_dias"]}
    itens: list[dict] = []
    for posicao in ctx["snapshot"]["posicoes"]:
        if posicao["tipo"] in portfolio.TIPOS_RENDA_FIXA:
            itens += _eventos_do_titulo(posicao, ctx["hoje"], marcos)
    itens.sort(key=lambda i: -i["relevancia"])
    return itens[: int(cfg["max"])]


def _eventos_do_titulo(posicao: dict, hoje: date, marcos: set[int]) -> list[dict]:
    """Eventos de um título: cupom pago hoje, cupom à vista e vencimento à vista."""
    itens = []
    if posicao.get("ultimo_pagamento") == hoje.isoformat():
        itens.append(_item_cupom_pago(posicao))

    dias_cupom = dias_ate(posicao.get("proximo_pagamento"), hoje)
    if dias_cupom in marcos:
        itens.append(_item_agenda(posicao, "💰", "paga juros", dias_cupom, "info"))

    if not posicao["vencido"] and posicao["dias_para_vencer"] in marcos:
        itens.append(
            _item_agenda(posicao, "📅", "vence", posicao["dias_para_vencer"], "atencao")
        )
    return itens


def _item_cupom_pago(posicao: dict) -> dict:
    """Cupom creditado na data de hoje — o único evento de caixa da carteira."""
    return _item(
        "calendario_rf",
        "💰",
        f"Cupom creditado — {posicao['descricao']}",
        f"{moeda(posicao['juros_recebidos_liquido'])} líquidos recebidos até aqui em "
        f"{posicao['pagamentos_realizados']} pagamento(s).",
        severidade="info",
        peso_pct=posicao["peso_pct"],
    )


def _item_agenda(posicao: dict, icone: str, verbo: str, dias: int, severidade: str) -> dict:
    """Marco de calendário de um título, com o valor que estará em jogo."""
    quando = "hoje" if dias == 0 else f"em {dias} dia(s)"
    return _item(
        "calendario_rf",
        icone,
        f"{posicao['descricao']} {verbo} {quando}",
        f"{formato.data_br(posicao['data_vencimento'])} · "
        f"{moeda(posicao['valor_liquido'])} líquidos estimados.",
        severidade=severidade,
        peso_pct=posicao["peso_pct"],
    )


# ─────────────────────────────────────────────
# Alertas do cálculo
# ─────────────────────────────────────────────

def _alertas(ctx: dict) -> list[dict]:
    """Alertas do cálculo que atingem a severidade mínima e ainda não saíram.

    Os que ficam abaixo do piso, ou fora do teto do bloco, não desaparecem:
    `relevancia._em_curso` os conta numa linha só. O filtro pelo que já foi
    enviado acontece **antes** do corte por `max`, de propósito: é o que faz o
    alerta de baixo, que nunca coube no teto, subir para a mensagem seguinte
    assim que o de cima é marcado como enviado — sem isso os primeiros da
    lista venceriam a disputa pelo teto para sempre, e o resto ficaria "em
    curso" indefinidamente, mesmo sem nunca ter sido mandado.
    """
    cfg = config_do_bloco(ctx["cfg"], "alertas")
    enviados = set(ctx["estado_envio"].get("alertas") or ())
    escolhidos = [
        a for a in ctx["snapshot"]["alertas"]
        if _passa_severidade(a["severidade"], cfg["severidade_minima"])
        and estado_envio.hash_alerta(a) not in enviados
    ]
    return [
        _item(
            "alertas",
            SEV_ICONE.get(a["severidade"], "•"),
            a["titulo"],
            a["descricao"],
            severidade=a["severidade"],
            chave_envio=estado_envio.hash_alerta(a),
        )
        for a in escolhidos[: int(cfg["max"])]
    ]


# ─────────────────────────────────────────────
# Leitura da IA
# ─────────────────────────────────────────────

def _fatos_ia(ctx: dict) -> list[dict]:
    """Fatos da IA filtrados por severidade, peso do ativo e o que já foi enviado.

    O piso de peso só vale para um fato sobre um ativo **da carteira**. Um fato
    setorial ou de mercado comparável (ex.: "Setor de papel", um fundo de fora
    da carteira citado como referência) não tem peso nenhum a medir — `ativo`
    nem está em `ctx["pesos"]` — e barrá-lo pelo piso descartaria uma leitura
    relevante que nunca teve como passar, só porque o campo não é um ticker
    da carteira.

    O filtro pelo estado de envio acontece antes do corte por `max`, para que
    um fato ainda não mandado suba na fila assim que o de cima for enviado —
    ver `_alertas`, que documenta o porquê.
    """
    cfg = config_do_bloco(ctx["cfg"], "fatos_ia")
    piso = float(cfg["peso_minimo_pct"])
    enviados = set(ctx["estado_envio"].get("fatos_ia") or ())
    itens = []
    for fato in ctx["ia"].get("fatos") or []:
        ativo = fato.get("ativo")
        peso = ctx["pesos"].get(ativo, 0.0)
        if not _passa_severidade(fato.get("severidade"), cfg["severidade_minima"]):
            continue
        if ativo in ctx["pesos"] and peso < piso:
            continue
        if estado_envio.hash_fato(fato) in enviados:
            continue
        itens.append(_item_fato(fato, peso))
    itens.sort(key=lambda i: -i["relevancia"])
    return itens[: int(cfg["max"])]


def _item_fato(fato: dict, peso: float) -> dict:
    return _item(
        "fatos_ia",
        SEV_ICONE.get(fato.get("severidade"), "ℹ️"),
        f"[{fato['ativo']}] {fato['titulo']}",
        fato["descricao"],
        severidade=fato.get("severidade", "info"),
        peso_pct=peso,
        chave_envio=estado_envio.hash_fato(fato),
    )


def _riscos_ia(ctx: dict) -> list[dict]:
    """Riscos da IA que atingem a severidade mínima e ainda não foram enviados.

    O filtro pelo estado de envio acontece antes do corte por `max` — ver
    `_alertas`, que documenta o porquê.
    """
    cfg = config_do_bloco(ctx["cfg"], "riscos_ia")
    enviados = set(ctx["estado_envio"].get("riscos_ia") or ())
    itens = []
    for risco in ctx["ia"].get("riscos") or []:
        if not _passa_severidade(risco.get("severidade"), cfg["severidade_minima"]):
            continue
        if estado_envio.hash_risco(risco) in enviados:
            continue
        ativos = risco.get("ativos") or []
        peso = max((ctx["pesos"].get(a, 0.0) for a in ativos), default=0.0)
        itens.append(_item_risco(risco, ativos, peso))
    itens.sort(key=lambda i: -i["relevancia"])
    return itens[: int(cfg["max"])]


def _item_risco(risco: dict, ativos: list[str], peso: float) -> dict:
    sufixo = f" ({', '.join(ativos)})" if ativos else ""
    return _item(
        "riscos_ia",
        SEV_ICONE.get(risco.get("severidade"), "⚠️"),
        f"{risco['titulo']}{sufixo}",
        risco["descricao"],
        severidade=risco.get("severidade", "info"),
        peso_pct=peso,
        chave_envio=estado_envio.hash_risco(risco),
    )


# ─────────────────────────────────────────────
# Indicadores fora da faixa
# ─────────────────────────────────────────────

def _indicadores(ctx: dict) -> list[dict]:
    """Médias da renda variável fora da faixa que o usuário aceita.

    O teto do FGC não entra aqui: `analysis._gerar_alertas` já o levanta com
    severidade `alerta`, e o bloco de alertas o publica.
    """
    cfg = config_do_bloco(ctx["cfg"], "indicadores")
    metricas = ctx["fundamentos"].get("metricas") or {}
    itens = []

    p_vp = metricas.get("p_vp_medio")
    if p_vp and not float(cfg["p_vp_minimo"]) <= p_vp <= float(cfg["p_vp_maximo"]):
        itens.append(_item_p_vp(p_vp, cfg))

    dy = metricas.get("dy_medio_pct")
    if dy and dy < float(cfg["dy_minimo_pct"]):
        itens.append(_item_dy(dy, metricas, cfg))
    return itens


def _item_p_vp(p_vp: float, cfg: dict) -> dict:
    """P/VP médio fora da faixa: desconto patrimonial ou ágio."""
    abaixo = p_vp < float(cfg["p_vp_minimo"])
    faixa = f"{formato.num(cfg['p_vp_minimo'], 2)} a {formato.num(cfg['p_vp_maximo'], 2)}"
    leitura = " — desconto patrimonial" if abaixo else " — ágio sobre o patrimônio"
    return _item(
        "indicadores",
        "🔎",
        f"P/VP médio em {formato.num(p_vp, 2)}{leitura}",
        f"Fora da faixa de {faixa} configurada para a renda variável.",
        severidade="info" if abaixo else "atencao",
    )


def _item_dy(dy: float, metricas: dict, cfg: dict) -> dict:
    """DY médio abaixo do piso configurado, com a renda que ele projeta."""
    return _item(
        "indicadores",
        "🔎",
        f"DY médio em {formato.pct(dy, 2, sinal=False)} a.a.",
        f"Abaixo do piso de {formato.pct(cfg['dy_minimo_pct'], 2, sinal=False)} · "
        f"renda estimada de {moeda(metricas.get('renda_mensal_estimada'))}/mês.",
        severidade="atencao",
    )


# ─────────────────────────────────────────────
# Ativo do dia, em rodízio
# ─────────────────────────────────────────────

def _aprofundamento(ctx: dict) -> list[dict]:
    """Ficha de uma posição por dia, em rodízio determinístico pela data.

    O índice sai do dia do ano: a carteira inteira cicla, o ativo do dia muda
    sozinho e nada precisa ser gravado. As fichas são ordenadas por ticker
    porque a ordem em que a IA as devolve não é estável entre execuções — sem
    isso o rodízio repetiria ou pularia ativos.
    """
    cfg = config_do_bloco(ctx["cfg"], "aprofundamento")
    fichas = sorted(ctx["fundamentos"].get("fichas") or [], key=lambda f: f["ticker"])
    if not fichas:
        return []

    quantas = min(max(1, int(cfg["por_dia"])), len(fichas))
    inicio = ctx["hoje"].timetuple().tm_yday * quantas
    return [_item_ficha(fichas[(inicio + i) % len(fichas)]) for i in range(quantas)]


def _primeiras_frases(texto: str, limite: int = LIMITE_COMENTARIO) -> str:
    """Início de um comentário, cortado no fim de uma frase.

    O comentário que a IA escreve por ativo tem parágrafos inteiros — e este é
    o bloco de enchimento do dia calmo, não a notícia. Deixá-lo por extenso
    faria dele o item mais longo da mensagem curta, que existe justamente para
    ser curta. O corte é na pontuação para não terminar no meio de uma oração.
    """
    texto = (texto or "").strip()
    if len(texto) <= limite:
        return texto

    corte = max(texto.rfind(p, 0, limite + 1) for p in (". ", "! ", "? "))
    return texto[: corte + 1] if corte > 0 else texto[:limite].rstrip() + "…"


def _item_ficha(ficha: dict) -> dict:
    """A posição da vez, com os atributos que a IA levantou e o comentário dela."""
    atributos = [
        ficha.get("segmento") or ficha.get("classificacao_rotulo"),
        f"P/VP {formato.num(ficha['p_vp'], 2)}" if ficha.get("p_vp") else None,
        f"DY {formato.pct(ficha['dy_12m_pct'], 1, sinal=False)}" if ficha.get("dy_12m_pct") else None,
    ]
    linha = " · ".join(a for a in atributos if a)
    comentario = _primeiras_frases(ficha.get("comentario", ""))
    return _item(
        "aprofundamento",
        "👁",
        f"Hoje na carteira: {ficha['ticker']}",
        f"{linha} — {comentario}".strip(" —"),
        severidade="info",
    )


# A ordem da tabela é a ordem de leitura da mensagem. `base` é o peso do bloco
# no corte por orçamento: o aprofundamento é o enchimento do dia calmo e sai
# primeiro; calendário, macro e alertas são os que mais custam se faltarem.
BLOCOS = (
    {"chave": "variacao_dia", "base": 2.0, "montar": _variacao_dia},
    {"chave": "macro", "base": 3.0, "montar": _macro},
    {"chave": "movimento", "base": 2.0, "montar": _movimento},
    {"chave": "calendario_rf", "base": 3.0, "montar": _calendario_rf},
    {"chave": "alertas", "base": 3.0, "montar": _alertas},
    {"chave": "fatos_ia", "base": 2.0, "montar": _fatos_ia},
    {"chave": "riscos_ia", "base": 2.0, "montar": _riscos_ia},
    {"chave": "indicadores", "base": 1.0, "montar": _indicadores},
    {"chave": "aprofundamento", "base": 0.5, "montar": _aprofundamento},
)

ORDEM_BLOCO = {bloco["chave"]: i for i, bloco in enumerate(BLOCOS)}

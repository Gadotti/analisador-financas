"""Seleção do que entra na mensagem curta do Telegram.

Este módulo decide **o que** merece ser enviado hoje; `analise.mensagem` decide
**como** aparece; `analise.gatilhos` sabe quando cada bloco tem algo a dizer.
A seleção é função pura do snapshot desta execução mais o cadastro: não lê
histórico, não guarda estado e não toca a rede — `hoje` é injetável.

É daí que vem a variação de um dia para o outro, sem nada memorizado. Cada
bloco tem um interruptor (`ativo`, no cadastro) e um limiar; o interruptor diz
se ele *pode* aparecer, o limiar diz se ele *merece* aparecer hoje. Na maioria
dos dias, a maioria dos blocos não dispara — e é por isso que a mensagem não
sai igual todo dia.

A única comparação com o passado é a dos indicadores macro, pedida
explicitamente: CDI, Selic meta e IPCA 12m mudam raramente e a mudança é a
notícia. O valor anterior vem de `runner`, que já abre a análise anterior por
outro motivo — nenhum arquivo novo, nenhuma leitura a mais.
"""

from __future__ import annotations

from datetime import date

from . import gatilhos, portfolio
from .gatilhos import BLOCOS, MACRO_COMPARADO, ORDEM_BLOCO, config_do_bloco

DIA_SEMANA = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")

# Janela do bloco semanal: o que vence ou paga cupom no próximo mês.
DIAS_AGENDA_SEMANAL = 30


# ─────────────────────────────────────────────
# Contorno — não passa pelo orçamento de itens
# ─────────────────────────────────────────────

def _estado(snapshot: dict) -> dict:
    """A âncora da mensagem: onde a carteira está, em uma linha."""
    totais = snapshot["totais"]
    return {
        "valor_atual": totais["valor_atual"],
        "resultado": totais["resultado"],
        "resultado_pct": totais["resultado_pct"],
        "resultado_dia": totais["resultado_dia"],
        "variacao_dia_pct": gatilhos.variacao_carteira_pct(totais),
        "saude": snapshot["saude_carteira"],
        "gerado_em": snapshot["gerado_em"],
    }


def _em_curso(snapshot: dict, escolhidos: list[dict]) -> int:
    """Alertas que existem mas não entraram — nem por severidade, nem por espaço."""
    publicados = sum(1 for i in escolhidos if i["bloco"] == "alertas")
    return max(len(snapshot["alertas"]) - publicados, 0)


def _resumo_ia(ctx: dict) -> str | None:
    """O sumário executivo da IA, só nos dias da semana configurados."""
    cfg = config_do_bloco(ctx["cfg"], "resumo_ia")
    if not cfg.get("ativo"):
        return None
    if ctx["hoje"].weekday() not in {int(d) for d in cfg["dias_semana"]}:
        return None
    return ctx["ia"].get("resumo") or None


def _semanal(ctx: dict) -> dict | None:
    """Fechamento do dia da semana escolhido: extremos e agenda do próximo mês.

    Não há comparação com a semana passada — isso exigiria dois pontos no
    tempo, e esta seleção não lê histórico. O que cabe sem estado é o resultado
    acumulado de cada ponta e o que vence ou paga cupom nos próximos
    `DIAS_AGENDA_SEMANAL` dias.
    """
    cfg = config_do_bloco(ctx["cfg"], "semanal")
    if not cfg.get("ativo") or ctx["hoje"].weekday() != int(cfg["dia_semana"]):
        return None

    destaques = ctx["snapshot"].get("destaques") or {}
    return {
        "dia": DIA_SEMANA[ctx["hoje"].weekday()],
        "melhor": _ponta(destaques.get("melhores")),
        "pior": _ponta(destaques.get("piores")),
        "agenda": _agenda(ctx["snapshot"], ctx["hoje"]),
    }


def _ponta(posicoes: list[dict] | None) -> dict | None:
    """Primeira posição de um extremo de `snapshot["destaques"]`."""
    if not posicoes:
        return None
    posicao = posicoes[0]
    return {"descricao": posicao["descricao"], "resultado_pct": posicao["resultado_pct"]}


def _agenda(snapshot: dict, hoje: date) -> list[dict]:
    """Vencimentos e cupons de renda fixa dentro da janela do bloco semanal."""
    agenda = []
    for posicao in snapshot["posicoes"]:
        if posicao["tipo"] not in portfolio.TIPOS_RENDA_FIXA or posicao["vencido"]:
            continue
        if posicao["dias_para_vencer"] <= DIAS_AGENDA_SEMANAL:
            agenda.append(_linha_agenda(posicao, "vence", posicao["data_vencimento"]))
        dias_cupom = gatilhos.dias_ate(posicao.get("proximo_pagamento"), hoje)
        if dias_cupom is not None and 0 <= dias_cupom <= DIAS_AGENDA_SEMANAL:
            agenda.append(_linha_agenda(posicao, "paga juros", posicao["proximo_pagamento"]))
    return sorted(agenda, key=lambda a: a["data"])


def _linha_agenda(posicao: dict, verbo: str, data_iso: str) -> dict:
    return {
        "descricao": posicao["descricao"],
        "verbo": verbo,
        "data": data_iso,
        "valor_liquido": posicao["valor_liquido"],
    }


# ─────────────────────────────────────────────
# Seleção
# ─────────────────────────────────────────────

def macro_comparavel(macro: dict | None) -> dict | None:
    """Só os indicadores que a mensagem compara, para guardar no registro.

    O `macro` inteiro traz índices e horário de consulta, que não entram em
    comparação nenhuma — e o registro é gravado em disco a cada execução.
    """
    macro = macro or {}
    recorte = {chave: macro[chave] for chave, _, _ in MACRO_COMPARADO if chave in macro}
    return recorte or None


def _no_orcamento(itens: list[dict], max_itens: int) -> list[dict]:
    """Corta pelo teto de itens e devolve na ordem de leitura da tabela.

    São dois critérios de propósito: quem entra é decidido pela relevância,
    quem vem antes é decidido pela ordem dos blocos. Ordenar a exibição pela
    relevância embaralharia as posições em movimento com os alertas.
    """
    escolhidos = sorted(itens, key=lambda i: -i["relevancia"])[: max(0, max_itens)]
    escolhidos.sort(key=lambda i: (ORDEM_BLOCO[i["bloco"]], -i["relevancia"]))
    return escolhidos


def _contexto(snapshot, ia, fundamentos, config, hoje, macro_anterior) -> dict:
    """O que todo bloco precisa ver, montado uma vez por execução."""
    return {
        "snapshot": snapshot,
        "ia": ia or {},
        "fundamentos": fundamentos or {},
        "cfg": portfolio.telegram_do_cadastro((config or {}).get("telegram")),
        "hoje": hoje or date.today(),
        "macro_anterior": macro_anterior or {},
        # Peso de cada ticker, para ponderar o que a IA escreveu sobre ele.
        "pesos": {p["ticker"]: p["peso_pct"] for p in snapshot["posicoes"] if p.get("ticker")},
    }


def _itens_dos_blocos(ctx: dict) -> list[dict]:
    """Roda cada bloco ligado e pontua o que ele devolveu com o peso do bloco."""
    itens: list[dict] = []
    for bloco in BLOCOS:
        if config_do_bloco(ctx["cfg"], bloco["chave"]).get("ativo"):
            itens += gatilhos.pontuar(bloco["montar"](ctx), bloco["base"])
    return itens


def selecionar(
    snapshot: dict,
    ia: dict | None = None,
    fundamentos: dict | None = None,
    config: dict | None = None,
    *,
    hoje: date | None = None,
    macro_anterior: dict | None = None,
) -> dict:
    """Monta a seleção do dia. `hoje` é injetável para os testes."""
    ctx = _contexto(snapshot, ia, fundamentos, config, hoje, macro_anterior)
    cfg = ctx["cfg"]
    escolhidos = _no_orcamento(_itens_dos_blocos(ctx), int(cfg["max_itens"]))

    return {
        "modo": "nada_novo" if not escolhidos else "resumo",
        "itens": escolhidos,
        "estado": _estado(snapshot),
        "alertas_em_curso": _em_curso(snapshot, escolhidos),
        "resumo_ia": _resumo_ia(ctx),
        "semanal": _semanal(ctx),
        "data": snapshot["data"],
        "ia_meta": (ia or {}).get("_meta") or {},
        "vale_enviar": bool(escolhidos) or not cfg["so_se_relevante"],
    }

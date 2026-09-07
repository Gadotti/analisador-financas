"""Consolidação da carteira: posições marcadas a mercado, alocação e alertas.

Esta camada é 100% determinística (sem IA) e não exige chave de API.
A análise qualitativa por IA vive em `analise.ai_insights` e é opcional.
"""

from __future__ import annotations

from datetime import date, datetime

from . import fixed_income, formato, market, portfolio, posicoes as marcacao

CLASSES = {"fii": "FIIs", "acao": "Ações", "cdb": "CDBs", "tesouro": "Tesouro Direto"}

# O FGC cobre depósito bancário; título público responde pelo Tesouro Nacional.
TIPOS_COM_FGC = ("cdb",)


# ─────────────────────────────────────────────
# Alertas determinísticos
# ─────────────────────────────────────────────

def _exposicao_por_emissor(posicoes: list[dict], tipos: tuple[str, ...]) -> dict[str, float]:
    """Soma o valor atual dos títulos ainda ativos por emissor."""
    por_emissor: dict[str, float] = {}
    for p in posicoes:
        if p["tipo"] in tipos and not p["vencido"]:
            por_emissor[p["emissor"]] = por_emissor.get(p["emissor"], 0.0) + p["valor_atual"]
    return por_emissor


def _cobertura_fgc(valor: float, limite_fgc: float, *, garantido: bool) -> dict:
    """Quanto o emissor consome do teto do FGC — nada, quando não é banco.

    O Tesouro Direto não é coberto pelo FGC: quem responde pelo papel é o
    próprio Tesouro Nacional, então não há teto a estourar.
    """
    if not garantido:
        return {"garantia": portfolio.EMISSOR_TESOURO, "fgc_limite": None,
                "fgc_uso_pct": None, "acima_do_fgc": False}
    return {
        "garantia": "FGC",
        "fgc_limite": limite_fgc,
        "fgc_uso_pct": round(valor / limite_fgc * 100, 1) if limite_fgc else 0.0,
        "acima_do_fgc": valor > limite_fgc,
    }


def _emissores_renda_fixa(posicoes: list[dict], base: float, limite_fgc: float) -> list[dict]:
    """Exposição por emissor de renda fixa, com o consumo do teto do FGC.

    É o recorte que falta em `fundamentals`, que só percorre fichas de renda
    variável: nenhum emissor de renda fixa aparece lá.

    `base` é o total de renda fixa (ver `_bases_concentracao`), não o da
    carteira: a pergunta que o recorte responde é como o dinheiro em renda fixa
    se divide entre Tesouro e bancos. Um título já vencido continua no total do
    regime mas sai do recorte, então os pesos podem somar menos de 100%.
    """
    emissores = [
        {
            "nome": nome,
            "valor": round(valor, 2),
            "peso_pct": round(valor / base * 100, 2) if base else 0.0,
            **_cobertura_fgc(valor, limite_fgc, garantido=nome != portfolio.EMISSOR_TESOURO),
        }
        for nome, valor in _exposicao_por_emissor(posicoes, portfolio.TIPOS_RENDA_FIXA).items()
    ]
    return sorted(emissores, key=lambda e: e["valor"], reverse=True)


def _bases_concentracao(posicoes: list[dict], total: float) -> dict[str, float]:
    """Total de cada regime — a base dos percentuais do quadro de alocação.

    Os recortes por ficha (classificação, segmento, gestora) pesam sobre o
    total de renda variável e os emissores sobre o total de renda fixa: diluir
    um FII na carteira inteira responde a outra pergunta, já respondida pela
    alocação por classe. O limite de concentração configurado vale sobre a base
    do recorte, a mesma do peso exibido — não sobre a carteira. A carteira
    entra na tabela porque a interface mostra o quanto cada regime representa.
    """
    def soma(tipos: tuple[str, ...]) -> float:
        return round(sum(p["valor_atual"] for p in posicoes if p["tipo"] in tipos), 2)

    return {
        "carteira": round(total, 2),
        "renda_variavel": soma(portfolio.TIPOS_VARIAVEL),
        "renda_fixa": soma(portfolio.TIPOS_RENDA_FIXA),
    }


def _alerta(severidade: str, titulo: str, descricao: str, alvo: str = "") -> dict:
    return {
        "severidade": severidade,
        "titulo": titulo,
        "descricao": descricao,
        "alvo": alvo,
        "origem": "calculo",
    }


def _gerar_alertas(posicoes: list[dict], total: float, config: dict) -> list[dict]:
    alertas: list[dict] = []

    limite_venc = int(config["alerta_vencimento_dias"])
    limite_conc = float(config["alerta_concentracao_pct"])
    limite_prej = float(config["alerta_prejuizo_pct"])
    limite_fgc = float(config["limite_fgc"])

    # 1. Vencimentos de renda fixa
    for p in posicoes:
        if p["tipo"] not in portfolio.TIPOS_RENDA_FIXA:
            continue
        dias = p["dias_para_vencer"]
        if p["vencido"]:
            alertas.append(_alerta(
                "alerta",
                f"{p['descricao']} venceu",
                f"Venceu em {formato.data_br(p['data_vencimento'])}. Valor liquido estimado de "
                f"{formato.moeda(p['valor_liquido'])} disponivel para reinvestimento.",
                p["descricao"],
            ))
        elif dias <= limite_venc:
            alertas.append(_alerta(
                "atencao",
                f"{p['descricao']} vence em {dias} dias",
                f"Vencimento em {formato.data_br(p['data_vencimento'])}. Planeje o reinvestimento de "
                f"{formato.moeda(p['valor_liquido'])} liquidos.",
                p["descricao"],
            ))

    # 2. Exposição por banco vs. teto do FGC — o Tesouro não é coberto por ele
    for banco, valor in _exposicao_por_emissor(posicoes, TIPOS_COM_FGC).items():
        if valor > limite_fgc:
            alertas.append(_alerta(
                "alerta",
                f"Exposicao ao {banco} acima do teto do FGC",
                f"{formato.moeda(valor)} aplicados no {banco}, acima do limite de "
                f"{formato.moeda(limite_fgc)} garantido pelo FGC por CPF/instituicao.",
                banco,
            ))

    # 3. Concentração por ativo
    if total > 0:
        for p in posicoes:
            peso = p["valor_atual"] / total * 100
            if peso > limite_conc:
                alertas.append(_alerta(
                    "atencao",
                    f"Concentracao em {p['descricao']}: {peso:.1f}%",
                    f"A posicao representa {peso:.1f}% da carteira, acima do limite de "
                    f"{limite_conc:.0f}% configurado.",
                    p["descricao"],
                ))

    # 4. Prejuízo relevante em renda variável
    for p in posicoes:
        if p["tipo"] in portfolio.TIPOS_VARIAVEL and p["resultado_pct"] <= -limite_prej:
            alertas.append(_alerta(
                "atencao",
                f"{p['descricao']} acumula {p['resultado_pct']:.1f}%",
                f"Preco medio {formato.moeda(p['preco_medio'])} contra cotacao atual "
                f"{formato.moeda(p['preco_atual'])}. Resultado de {formato.moeda(p['resultado'])}.",
                p["descricao"],
            ))

    # 5. Falhas de cotação
    sem_cotacao = [p["descricao"] for p in posicoes if p.get("erro_cotacao")]
    if sem_cotacao:
        alertas.append(_alerta(
            "info",
            "Cotacao indisponivel",
            f"Nao foi possivel obter a cotacao de: {', '.join(sem_cotacao)}. "
            f"Estas posicoes entraram na carteira pelo preco medio.",
            ", ".join(sem_cotacao),
        ))

    ordem = {"alerta": 0, "atencao": 1, "info": 2}
    alertas.sort(key=lambda a: ordem.get(a["severidade"], 3))
    return alertas


def _saude(alertas: list[dict], resultado_pct: float) -> str:
    if any(a["severidade"] == "alerta" for a in alertas):
        return "alerta"
    qtd_atencao = sum(1 for a in alertas if a["severidade"] == "atencao")
    if qtd_atencao >= 3 or resultado_pct <= -10:
        return "atencao"
    if qtd_atencao == 0 and resultado_pct >= 5:
        return "otima"
    return "boa"


# ─────────────────────────────────────────────
# Snapshot completo
# ─────────────────────────────────────────────

def consolidar(carteira: dict | None = None, *, usar_cache: bool = True) -> dict:
    """Calcula o estado atual da carteira. Não usa IA."""
    carteira = carteira or portfolio.load()
    config = carteira["config"]
    hoje = date.today()

    macro = market.cenario_macro()

    tickers = portfolio.tickers(carteira)
    cots = market.cotacoes(tickers, usar_cache=usar_cache) if tickers else {}

    titulos = [p for p in carteira["posicoes"] if p["tipo"] == "tesouro"]
    tesouro = marcacao.dados_do_tesouro(titulos, usar_cache=usar_cache) if titulos else {}

    posicoes: list[dict] = []
    for pos in carteira["posicoes"]:
        if pos["tipo"] in portfolio.TIPOS_VARIAVEL:
            posicoes.append(marcacao.variavel(pos, cots.get(pos["ticker"], {})))
        else:
            posicoes.append(marcacao.renda_fixa(pos, hoje, macro, tesouro.get(pos["id"])))

    total_investido = sum(p["valor_investido"] for p in posicoes)
    total_atual = sum(p["valor_atual"] for p in posicoes)
    resultado = total_atual - total_investido
    resultado_pct = (resultado / total_investido * 100) if total_investido else 0.0
    resultado_dia = sum(p.get("resultado_dia") or 0 for p in posicoes)

    for p in posicoes:
        p["peso_pct"] = round(p["valor_atual"] / total_atual * 100, 2) if total_atual else 0.0

    # Alocação por classe
    classes = {}
    for chave, rotulo in CLASSES.items():
        itens = [p for p in posicoes if p["tipo"] == chave]
        if not itens:
            continue
        valor = sum(p["valor_atual"] for p in itens)
        investido = sum(p["valor_investido"] for p in itens)
        classes[chave] = {
            "rotulo": rotulo,
            "posicoes": len(itens),
            "valor_investido": round(investido, 2),
            "valor_atual": round(valor, 2),
            "resultado": round(valor - investido, 2),
            "resultado_pct": round((valor - investido) / investido * 100, 2) if investido else 0.0,
            "peso_pct": round(valor / total_atual * 100, 2) if total_atual else 0.0,
        }

    bases = _bases_concentracao(posicoes, total_atual)
    alertas = _gerar_alertas(posicoes, total_atual, config)

    variaveis = [p for p in posicoes if p["tipo"] in portfolio.TIPOS_VARIAVEL and not p.get("erro_cotacao")]
    destaques = sorted(variaveis, key=lambda p: p["resultado_pct"], reverse=True)

    return {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "data": hoje.isoformat(),
        "perfil": carteira.get("perfil", ""),
        "totais": {
            "valor_investido": round(total_investido, 2),
            "valor_atual": round(total_atual, 2),
            "resultado": round(resultado, 2),
            "resultado_pct": round(resultado_pct, 2),
            "resultado_dia": round(resultado_dia, 2),
            "posicoes": len(posicoes),
        },
        "classes": classes,
        # Uma régua só: todo consumidor lê daqui o limite que o usuário configurou.
        "limite_concentracao_pct": float(config["alerta_concentracao_pct"]),
        # E uma base por regime, para os recortes do quadro de alocação.
        "bases_concentracao": bases,
        "emissores_renda_fixa": _emissores_renda_fixa(
            posicoes, bases["renda_fixa"], float(config["limite_fgc"])
        ),
        "posicoes": posicoes,
        "alertas": alertas,
        "saude_carteira": _saude(alertas, resultado_pct),
        "destaques": {
            "melhores": destaques[:3],
            "piores": destaques[-3:][::-1] if len(destaques) > 3 else [],
        },
        "macro": macro,
        # A tabela de IR vem junto porque a interface compara ofertas isentas
        # (LCI, LCA) com tributadas; a alíquota tem de ser a mesma do resgate.
        "ir_renda_fixa": fixed_income.faixas_ir(),
    }


# A formatação mora em `analise.formato`; aqui ela é só reexportada, porque os
# alertas descrevem valores em reais e datas no meio do texto.
moeda = formato.moeda
data_br = formato.data_br

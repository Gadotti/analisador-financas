"""Marcação a mercado aproximada de renda fixa: CDB, LCI, LCA e Tesouro Direto.

Convenções adotadas (padrão do mercado brasileiro):
  - Rendimento capitalizado em dias úteis (base 252) para CDI, Selic e
    prefixado. O papel bancário rende um percentual do CDI; o Tesouro Selic
    rende a Selic mais um ágio ou deságio somado à taxa.
  - IPCA+ multiplica o IPCA acumulado do período pelo juro real, este
    também capitalizado em dias úteis (base 252).
  - IR regressivo sobre o rendimento, conforme prazo da aplicação — exceto
    em LCI e LCA, isentas para a pessoa física.
  - Com cupom periódico, cada aniversário da aplicação paga o rendimento do
    período e o principal segue intacto: não há capitalização de um período
    para o outro, e o IR é retido em cada pagamento pelo prazo decorrido até
    ele.
  - Só o Tesouro Direto paga custódia à B3, descontada do valor líquido.

Os valores são ESTIMATIVAS: as taxas usadas são as vigentes hoje, projetadas
para todo o período decorrido. O Tesouro ainda troca essa curva pelo preço de
revenda do pregão em `marcar_a_mercado`; o papel bancário não tem preço
publicado, e para ele a curva é o que resta. O extrato da instituição é a
fonte oficial.
"""

from __future__ import annotations

from datetime import date, timedelta

PAGAMENTO_VENCIMENTO = "vencimento"
PAGAMENTO_MENSAL = "mensal"
PAGAMENTO_SEMESTRAL = "semestral"

# Meses entre um cupom e o seguinte, por forma de pagamento.
INTERVALO_CUPOM = {PAGAMENTO_MENSAL: 1, PAGAMENTO_SEMESTRAL: 6}

# Taxa de custódia da B3 sobre o Tesouro Direto, isenta na primeira faixa
# aplicada em Tesouro Selic (a isenção é por CPF; aqui vale por posição).
CUSTODIA_B3_AA_PCT = 0.20
CUSTODIA_ISENTA_SELIC = 10000.0

# Alíquotas de IR sobre renda fixa (dias corridos da aplicação)
TABELA_IR = (
    (180, 0.225),
    (360, 0.20),
    (720, 0.175),
    (float("inf"), 0.15),
)

# O que muda de um tipo de título para o outro na hora de liquidar. São só dois
# eixos, e nenhum deles é opinião:
#
#   - LCI e LCA são isentas de IR para a pessoa física (Lei 11.033/2004, art.
#     3º, II), então a taxa contratada nelas já é líquida;
#   - só o Tesouro Direto paga custódia à B3 — o papel bancário não é
#     custodiado lá.
#
# Um tipo novo de renda fixa entra nesta tabela, não num `if` no meio do
# cálculo. Espelha `REGRAS` de `src/core/rendaFixa.js`, que declara o cadastro.
REGIME = {
    "cdb": {"isento_ir": False, "custodia_b3": False},
    "lci": {"isento_ir": True, "custodia_b3": False},
    "lca": {"isento_ir": True, "custodia_b3": False},
    "tesouro": {"isento_ir": False, "custodia_b3": True},
}


def regime(tipo: str) -> dict:
    """Como o título é tributado e se paga custódia à B3."""
    try:
        return REGIME[tipo]
    except KeyError:
        raise ValueError(
            f"Tipo de renda fixa desconhecido: {tipo!r}. Use: {', '.join(REGIME)}."
        ) from None


# ─────────────────────────────────────────────
# Calendário
# ─────────────────────────────────────────────

def _pascoa(ano: int) -> date:
    """Domingo de Páscoa pelo algoritmo de Meeus/Jones/Butcher."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


def feriados_nacionais(ano: int) -> set[date]:
    """Feriados nacionais brasileiros, incluindo os móveis (base Páscoa)."""
    pascoa = _pascoa(ano)
    return {
        date(ano, 1, 1),                 # Confraternização Universal
        pascoa - timedelta(days=48),     # Carnaval (segunda)
        pascoa - timedelta(days=47),     # Carnaval (terça)
        pascoa - timedelta(days=2),      # Sexta-feira Santa
        date(ano, 4, 21),                # Tiradentes
        date(ano, 5, 1),                 # Dia do Trabalho
        pascoa + timedelta(days=60),     # Corpus Christi
        date(ano, 9, 7),                 # Independência
        date(ano, 10, 12),               # Nossa Senhora Aparecida
        date(ano, 11, 2),                # Finados
        date(ano, 11, 15),               # Proclamação da República
        date(ano, 11, 20),               # Consciência Negra
        date(ano, 12, 25),               # Natal
    }


def dias_uteis(inicio: date, fim: date) -> int:
    """Dias úteis entre duas datas (exclui o dia inicial, inclui o final)."""
    if fim <= inicio:
        return 0
    feriados: set[date] = set()
    for ano in range(inicio.year, fim.year + 1):
        feriados |= feriados_nacionais(ano)

    total = 0
    atual = inicio + timedelta(days=1)
    while atual <= fim:
        if atual.weekday() < 5 and atual not in feriados:
            total += 1
        atual += timedelta(days=1)
    return total


def proximo_dia_util(dia: date) -> date:
    """Primeiro dia útil a partir de `dia`, inclusive."""
    feriados = feriados_nacionais(dia.year) | feriados_nacionais(dia.year + 1)
    while dia.weekday() >= 5 or dia in feriados:
        dia += timedelta(days=1)
    return dia


def somar_meses(inicio: date, meses: int) -> date:
    """Mesmo dia do mês `meses` à frente, encurtando quando o mês é menor."""
    total = inicio.month - 1 + meses
    ano, mes = inicio.year + total // 12, total % 12 + 1
    ultimo_dia = (date(ano + mes // 12, mes % 12 + 1, 1) - timedelta(days=1)).day
    return date(ano, mes, min(inicio.day, ultimo_dia))


def datas_pagamento(
    aplicacao: date, vencimento: date, ate: date, intervalo_meses: int = 1
) -> list[date]:
    """Aniversários da aplicação já pagos até `ate`, em dia útil.

    `intervalo_meses` é 1 para o cupom mensal e 6 para o semestral.
    """
    datas: list[date] = []
    periodo = 1
    while True:
        prevista = proximo_dia_util(somar_meses(aplicacao, periodo * intervalo_meses))
        if prevista > vencimento or prevista > ate:
            return datas
        datas.append(prevista)
        periodo += 1


def aliquota_ir(dias_corridos: int) -> float:
    for limite, aliquota in TABELA_IR:
        if dias_corridos <= limite:
            return aliquota
    return 0.15


def _aliquota(dias_corridos: int, *, isento: bool) -> float:
    """Alíquota que de fato incide: zero no papel isento, a tabela nos demais."""
    return 0.0 if isento else aliquota_ir(dias_corridos)


def _rotulo_faixa(inicio: int, fim: int | None) -> str:
    if fim is None:
        return f"acima de {inicio} dias"
    if inicio == 0:
        return f"até {fim} dias"
    return f"de {inicio + 1} a {fim} dias"


def faixas_ir() -> list[dict]:
    """`TABELA_IR` em forma serializável, para quem só precisa exibi-la.

    A alíquota é a mesma régua que `_liquidar` aplica no resgate. Publicá-la no
    snapshot evita que a interface mantenha uma cópia própria da tabela e passe
    a divergir daqui quando a legislação mudar.
    """
    faixas: list[dict] = []
    inicio = 0
    for limite, aliquota in TABELA_IR:
        fim = None if limite == float("inf") else int(limite)
        faixas.append({
            "de_dias": inicio + 1,
            "ate_dias": fim,
            "aliquota_pct": round(aliquota * 100, 2),
            "rotulo": _rotulo_faixa(inicio, fim),
        })
        inicio = fim if fim is not None else inicio
    return faixas


# ─────────────────────────────────────────────
# Fatores de rendimento
# ─────────────────────────────────────────────

def _taxa_efetiva(
    indexador: str, taxa: float, cdi_anual_pct: float, selic_anual_pct: float
) -> float:
    """Taxa anual que de fato remunera o título, em % a.a.

    O CDB rende um percentual do CDI (110% do CDI); o Tesouro Selic rende a
    Selic mais o ágio ou deságio contratado (Selic + 0,09% a.a.). Prefixado e
    IPCA+ usam a taxa como está.
    """
    if indexador == "CDI":
        return cdi_anual_pct * (taxa / 100)
    if indexador == "SELIC":
        return selic_anual_pct + taxa
    return taxa


def _fator_periodo(
    taxa_efetiva: float, du: int, du_total: int, correcao: float | None
) -> float:
    """Fator de um trecho do prazo, com `du` dias úteis na base 252.

    A correção monetária acumulada (IPCA+) vale para todo o período decorrido;
    para reparti-la entre os trechos, ela é distribuída na proporção dos dias
    úteis de cada um — uma estimativa, já que o índice não é linear no tempo.
    """
    fator = (1 + taxa_efetiva / 100) ** (du / 252)
    if correcao and du_total:
        fator *= correcao ** (du / du_total)
    return fator


# ─────────────────────────────────────────────
# Custódia
# ─────────────────────────────────────────────

def _liquidar(
    valor_bruto: float, principal: float, *, tipo: str, indexador: str, dc: int, du: int
) -> dict:
    """Desconta do valor bruto o que sai na hora do resgate: IR e custódia.

    Vale tanto para o valor na curva quanto para o de mercado — o que muda é o
    `valor_bruto` de entrada, porque o IR incide sobre o ganho efetivamente
    realizado em cada um deles.
    """
    regras = regime(tipo)
    rendimento = valor_bruto - principal
    ir_pct = _aliquota(dc, isento=regras["isento_ir"])
    ir_valor = max(rendimento, 0) * ir_pct
    custodia = _custodia_b3(regras, indexador, valor_bruto, du)
    return {
        "ir_aliquota_pct": round(ir_pct * 100, 2),
        "ir_valor": round(ir_valor, 2),
        "custodia_valor": round(custodia, 2),
        "valor_liquido": valor_bruto - ir_valor - custodia,
    }


def _custodia_b3(regras: dict, indexador: str, valor_bruto: float, du: int) -> float:
    """Custódia da B3 acumulada no período, só para o Tesouro Direto.

    A cobrança incide sobre o valor da posição; em Tesouro Selic, a primeira
    faixa é isenta.
    """
    if not regras["custodia_b3"]:
        return 0.0
    base = valor_bruto
    if indexador == "SELIC":
        base = max(valor_bruto - CUSTODIA_ISENTA_SELIC, 0.0)
    return base * ((1 + CUSTODIA_B3_AA_PCT / 100) ** (du / 252) - 1)


# ─────────────────────────────────────────────
# Cupons periódicos
# ─────────────────────────────────────────────

def _sem_pagamentos(aplicacao: date) -> dict:
    """Cronograma de quem não paga juros no meio do caminho."""
    return {
        "desde": aplicacao,
        "quantidade": 0,
        "bruto": 0.0,
        "ir": 0.0,
        "proximo": None,
        "ultimo": None,
    }


def _proximo_pagamento(
    aplicacao: date, vencimento: date, pagos: int, intervalo_meses: int
) -> date | None:
    """Aniversário seguinte ao último pago, ou None se passa do vencimento."""
    prevista = proximo_dia_util(somar_meses(aplicacao, (pagos + 1) * intervalo_meses))
    return prevista if prevista <= vencimento else None


def _juros_recebidos(
    principal: float,
    aplicacao: date,
    vencimento: date,
    referencia: date,
    *,
    taxa_efetiva: float,
    correcao: float | None,
    du_total: int,
    intervalo_meses: int,
    isento_ir: bool,
) -> dict:
    """Soma os juros já pagos nos aniversários do título, com o IR de cada um."""
    datas = datas_pagamento(aplicacao, vencimento, referencia, intervalo_meses)
    bruto = ir = 0.0
    desde = aplicacao
    for pagamento in datas:
        du = dias_uteis(desde, pagamento)
        juros = principal * (_fator_periodo(taxa_efetiva, du, du_total, correcao) - 1)
        bruto += juros
        ir += juros * _aliquota((pagamento - aplicacao).days, isento=isento_ir)
        desde = pagamento
    return {
        "desde": desde,
        "quantidade": len(datas),
        "bruto": bruto,
        "ir": ir,
        "proximo": _proximo_pagamento(aplicacao, vencimento, len(datas), intervalo_meses),
        "ultimo": datas[-1] if datas else None,
    }


# ─────────────────────────────────────────────
# Valorização
# ─────────────────────────────────────────────

def _aviso_indexador(
    indexador: str, ipca_fator: float | None, selic_anual_pct: float | None
) -> str | None:
    """Avisa quando o indexador do título não pôde ser consultado."""
    if indexador == "IPCA" and ipca_fator is None:
        return "IPCA indisponivel - considerado apenas o juro real."
    if indexador == "SELIC" and not selic_anual_pct:
        return "Selic indisponivel - considerado apenas o agio contratado."
    return None


def valorizar(
    titulo: dict,
    *,
    hoje: date | None = None,
    cdi_anual_pct: float,
    selic_anual_pct: float | None = None,
    ipca_fator: float | None = None,
) -> dict:
    """Calcula o valor atual estimado de um título de renda fixa.

    `valor_bruto` é o que ainda está aplicado no papel. Num título com cupom
    periódico isso é o principal mais o rendimento do período em curso — o que
    já foi pago saiu da posição e aparece em `juros_recebidos_*`.

    Args:
        titulo: posição normalizada de um dos tipos de `REGIME`.
        hoje: data de referência (padrão: data corrente).
        cdi_anual_pct: CDI anualizado vigente, em % a.a.
        selic_anual_pct: meta Selic vigente, em % a.a. (só para Tesouro Selic).
        ipca_fator: fator acumulado do IPCA desde a aplicação (só para IPCA+).
    """
    hoje = hoje or date.today()
    aplicacao = date.fromisoformat(titulo["data_aplicacao"])
    vencimento = date.fromisoformat(titulo["data_vencimento"])

    # Após o vencimento o título para de render
    referencia = min(hoje, vencimento)

    tipo = titulo.get("tipo") or "cdb"
    regras = regime(tipo)
    principal = float(titulo["valor_inicial"])
    indexador = titulo["indexador"]
    taxa_efetiva = _taxa_efetiva(
        indexador, float(titulo["taxa"]), cdi_anual_pct, selic_anual_pct or 0.0
    )
    correcao = ipca_fator if indexador == "IPCA" else None
    aviso = _aviso_indexador(indexador, ipca_fator, selic_anual_pct)

    du_total = dias_uteis(aplicacao, referencia)
    dc = max((referencia - aplicacao).days, 0)
    pagamento = titulo.get("pagamento_juros") or PAGAMENTO_VENCIMENTO
    intervalo = INTERVALO_CUPOM.get(pagamento)

    if intervalo:
        recebidos = _juros_recebidos(
            principal, aplicacao, vencimento, referencia,
            taxa_efetiva=taxa_efetiva, correcao=correcao, du_total=du_total,
            intervalo_meses=intervalo, isento_ir=regras["isento_ir"],
        )
    else:
        recebidos = _sem_pagamentos(aplicacao)

    fator = _fator_periodo(
        taxa_efetiva, dias_uteis(recebidos["desde"], referencia), du_total, correcao
    )
    valor_bruto = principal * fator
    rendimento_bruto = valor_bruto - principal
    liquidacao = _liquidar(
        valor_bruto, principal, tipo=tipo, indexador=indexador, dc=dc, du=du_total
    )
    valor_liquido = liquidacao["valor_liquido"]
    rendimento_liquido = valor_liquido - principal

    recebido_liquido = recebidos["bruto"] - recebidos["ir"]
    total_bruto = rendimento_bruto + recebidos["bruto"]
    total_liquido = rendimento_liquido + recebido_liquido
    proximo = recebidos["proximo"]
    ultimo = recebidos["ultimo"]

    return {
        "valor_inicial": round(principal, 2),
        "valor_bruto": round(valor_bruto, 2),
        "valor_liquido": round(valor_liquido, 2),
        "rendimento_bruto": round(rendimento_bruto, 2),
        "rendimento_liquido": round(rendimento_liquido, 2),
        "rentabilidade_bruta_pct": round((fator - 1) * 100, 4),
        "rentabilidade_liquida_pct": round(rendimento_liquido / principal * 100, 4),
        "pagamento_juros": pagamento,
        "pagamentos_realizados": recebidos["quantidade"],
        "proximo_pagamento": proximo.isoformat() if proximo else None,
        # Data do último cupom já pago. É calendário puro, derivado do mesmo
        # cronograma: permite anunciar "cupom creditado hoje" sem consultar
        # nenhum histórico de execuções anteriores.
        "ultimo_pagamento": ultimo.isoformat() if ultimo else None,
        "juros_recebidos_bruto": round(recebidos["bruto"], 2),
        "juros_recebidos_ir": round(recebidos["ir"], 2),
        "juros_recebidos_liquido": round(recebido_liquido, 2),
        "rendimento_total_bruto": round(total_bruto, 2),
        "rendimento_total_liquido": round(total_liquido, 2),
        "rentabilidade_total_bruta_pct": round(total_bruto / principal * 100, 4),
        "rentabilidade_total_liquida_pct": round(total_liquido / principal * 100, 4),
        "taxa_efetiva_aa_pct": round(taxa_efetiva, 4),
        "ir_aliquota_pct": liquidacao["ir_aliquota_pct"],
        "ir_valor": liquidacao["ir_valor"],
        "custodia_valor": liquidacao["custodia_valor"],
        # Num papel isento a taxa contratada já é líquida: quem exibe o título
        # precisa dizer isso, senão um 95% do CDI parece pior do que é.
        "isento_ir": regras["isento_ir"],
        "indexador_liquidacao": indexador,
        "valor_na_curva": round(valor_bruto, 2),
        "dias_corridos": dc,
        "dias_uteis": du_total,
        "dias_para_vencer": (vencimento - hoje).days,
        "vencido": hoje >= vencimento,
        "aviso": aviso,
    }


# ─────────────────────────────────────────────
# Marcação a mercado
# ─────────────────────────────────────────────

def marcar_a_mercado(curva: dict, *, quantidade: float, pu_venda: float) -> dict:
    """Reescreve o resultado de `valorizar` com o preço de revenda de hoje.

    O que o Tesouro paga por um título antes do vencimento é o PU de venda —
    e ele já reflete só os fluxos que faltam, então cupom já pago continua
    fora daqui, como no cálculo da curva. O valor na curva não é descartado:
    vai para `valor_na_curva`, porque é ele que diz quanto o papel rende para
    quem carrega até o fim.

    Args:
        curva: retorno de `valorizar` para o mesmo título.
        quantidade: títulos detidos, geralmente fracionários.
        pu_venda: preço unitário de revenda ao Tesouro, do último pregão.
    """
    principal = curva["valor_inicial"]
    valor_bruto = quantidade * pu_venda
    rendimento_bruto = valor_bruto - principal

    liquidacao = _liquidar(
        valor_bruto,
        principal,
        tipo="tesouro",
        indexador=curva["indexador_liquidacao"],
        dc=curva["dias_corridos"],
        du=curva["dias_uteis"],
    )
    rendimento_liquido = liquidacao["valor_liquido"] - principal
    total_bruto = rendimento_bruto + curva["juros_recebidos_bruto"]
    total_liquido = rendimento_liquido + curva["juros_recebidos_liquido"]

    return {
        **curva,
        "valor_na_curva": curva["valor_bruto"],
        "valor_bruto": round(valor_bruto, 2),
        "valor_liquido": round(liquidacao["valor_liquido"], 2),
        "rendimento_bruto": round(rendimento_bruto, 2),
        "rendimento_liquido": round(rendimento_liquido, 2),
        "rentabilidade_bruta_pct": round(rendimento_bruto / principal * 100, 4),
        "rentabilidade_liquida_pct": round(rendimento_liquido / principal * 100, 4),
        "rendimento_total_bruto": round(total_bruto, 2),
        "rendimento_total_liquido": round(total_liquido, 2),
        "rentabilidade_total_bruta_pct": round(total_bruto / principal * 100, 4),
        "rentabilidade_total_liquida_pct": round(total_liquido / principal * 100, 4),
        "ir_aliquota_pct": liquidacao["ir_aliquota_pct"],
        "ir_valor": liquidacao["ir_valor"],
        "custodia_valor": liquidacao["custodia_valor"],
        "quantidade": round(quantidade, 6),
        "pu_venda": round(pu_venda, 2),
    }

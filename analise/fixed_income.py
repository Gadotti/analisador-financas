"""Marcação a mercado aproximada de CDBs.

Convenções adotadas (padrão do mercado brasileiro):
  - Rendimento capitalizado em dias úteis (base 252) para CDI e prefixado.
  - IPCA+ multiplica o IPCA acumulado do período pelo juro real, este
    também capitalizado em dias úteis (base 252).
  - IR regressivo sobre o rendimento, conforme prazo da aplicação.
  - Com juros mensais, cada aniversário da aplicação paga o rendimento do
    período e o principal segue intacto: não há capitalização de um mês para
    o outro, e o IR é retido em cada pagamento pelo prazo decorrido até ele.

Os valores são ESTIMATIVAS: a taxa CDI usada é a vigente hoje, projetada
para todo o período decorrido. O extrato do banco é sempre a fonte oficial.
"""

from __future__ import annotations

from datetime import date, timedelta

PAGAMENTO_VENCIMENTO = "vencimento"
PAGAMENTO_MENSAL = "mensal"

# Alíquotas de IR sobre renda fixa (dias corridos da aplicação)
TABELA_IR = (
    (180, 0.225),
    (360, 0.20),
    (720, 0.175),
    (float("inf"), 0.15),
)


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


def datas_pagamento(aplicacao: date, vencimento: date, ate: date) -> list[date]:
    """Aniversários mensais da aplicação já pagos até `ate`, em dia útil."""
    datas: list[date] = []
    mes = 1
    while True:
        prevista = proximo_dia_util(somar_meses(aplicacao, mes))
        if prevista > vencimento or prevista > ate:
            return datas
        datas.append(prevista)
        mes += 1


def aliquota_ir(dias_corridos: int) -> float:
    for limite, aliquota in TABELA_IR:
        if dias_corridos <= limite:
            return aliquota
    return 0.15


# ─────────────────────────────────────────────
# Fatores de rendimento
# ─────────────────────────────────────────────

def _taxa_efetiva(indexador: str, taxa: float, cdi_anual_pct: float) -> float:
    """Taxa anual que de fato remunera o título, em % a.a."""
    if indexador == "CDI":
        return cdi_anual_pct * (taxa / 100)
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
# Juros mensais
# ─────────────────────────────────────────────

def _sem_pagamentos(aplicacao: date) -> dict:
    """Cronograma de quem não paga juros no meio do caminho."""
    return {"desde": aplicacao, "quantidade": 0, "bruto": 0.0, "ir": 0.0, "proximo": None}


def _proximo_pagamento(aplicacao: date, vencimento: date, pagos: int) -> date | None:
    """Aniversário seguinte ao último pago, ou None se passa do vencimento."""
    prevista = proximo_dia_util(somar_meses(aplicacao, pagos + 1))
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
) -> dict:
    """Soma os juros já pagos nos aniversários mensais, com o IR de cada um."""
    datas = datas_pagamento(aplicacao, vencimento, referencia)
    bruto = ir = 0.0
    desde = aplicacao
    for pagamento in datas:
        du = dias_uteis(desde, pagamento)
        juros = principal * (_fator_periodo(taxa_efetiva, du, du_total, correcao) - 1)
        bruto += juros
        ir += juros * aliquota_ir((pagamento - aplicacao).days)
        desde = pagamento
    return {
        "desde": desde,
        "quantidade": len(datas),
        "bruto": bruto,
        "ir": ir,
        "proximo": _proximo_pagamento(aplicacao, vencimento, len(datas)),
    }


# ─────────────────────────────────────────────
# Valorização
# ─────────────────────────────────────────────

def valorizar(
    cdb: dict,
    *,
    hoje: date | None = None,
    cdi_anual_pct: float,
    ipca_fator: float | None = None,
) -> dict:
    """Calcula o valor atual estimado de um CDB.

    `valor_bruto` é o que ainda está aplicado no título. Num CDB de juros
    mensais isso é o principal mais o rendimento do mês em curso — o que já
    foi pago saiu da posição e aparece em `juros_recebidos_*`.

    Args:
        cdb: posição normalizada do tipo "cdb".
        hoje: data de referência (padrão: data corrente).
        cdi_anual_pct: CDI anualizado vigente, em % a.a.
        ipca_fator: fator acumulado do IPCA desde a aplicação (só para IPCA+).
    """
    hoje = hoje or date.today()
    aplicacao = date.fromisoformat(cdb["data_aplicacao"])
    vencimento = date.fromisoformat(cdb["data_vencimento"])

    # Após o vencimento o título para de render
    referencia = min(hoje, vencimento)

    principal = float(cdb["valor_inicial"])
    indexador = cdb["indexador"]
    taxa_efetiva = _taxa_efetiva(indexador, float(cdb["taxa"]), cdi_anual_pct)
    correcao = ipca_fator if indexador == "IPCA" else None
    aviso = (
        "IPCA indisponivel - considerado apenas o juro real."
        if indexador == "IPCA" and ipca_fator is None
        else None
    )

    du_total = dias_uteis(aplicacao, referencia)
    dc = max((referencia - aplicacao).days, 0)
    pagamento = cdb.get("pagamento_juros") or PAGAMENTO_VENCIMENTO

    if pagamento == PAGAMENTO_MENSAL:
        recebidos = _juros_recebidos(
            principal, aplicacao, vencimento, referencia,
            taxa_efetiva=taxa_efetiva, correcao=correcao, du_total=du_total,
        )
    else:
        recebidos = _sem_pagamentos(aplicacao)

    fator = _fator_periodo(
        taxa_efetiva, dias_uteis(recebidos["desde"], referencia), du_total, correcao
    )
    valor_bruto = principal * fator
    rendimento_bruto = valor_bruto - principal
    ir_pct = aliquota_ir(dc)
    ir_valor = max(rendimento_bruto, 0) * ir_pct
    valor_liquido = valor_bruto - ir_valor
    rendimento_liquido = valor_liquido - principal

    recebido_liquido = recebidos["bruto"] - recebidos["ir"]
    total_bruto = rendimento_bruto + recebidos["bruto"]
    total_liquido = rendimento_liquido + recebido_liquido
    proximo = recebidos["proximo"]

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
        "juros_recebidos_bruto": round(recebidos["bruto"], 2),
        "juros_recebidos_ir": round(recebidos["ir"], 2),
        "juros_recebidos_liquido": round(recebido_liquido, 2),
        "rendimento_total_bruto": round(total_bruto, 2),
        "rendimento_total_liquido": round(total_liquido, 2),
        "rentabilidade_total_bruta_pct": round(total_bruto / principal * 100, 4),
        "rentabilidade_total_liquida_pct": round(total_liquido / principal * 100, 4),
        "taxa_efetiva_aa_pct": round(taxa_efetiva, 4),
        "ir_aliquota_pct": round(ir_pct * 100, 2),
        "ir_valor": round(ir_valor, 2),
        "dias_corridos": dc,
        "dias_uteis": du_total,
        "dias_para_vencer": (vencimento - hoje).days,
        "vencido": hoje >= vencimento,
        "aviso": aviso,
    }

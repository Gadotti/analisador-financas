"""Marcação a mercado aproximada de CDBs.

Convenções adotadas (padrão do mercado brasileiro):
  - Rendimento capitalizado em dias úteis (base 252) para CDI e prefixado.
  - IPCA+ usa o IPCA acumulado do período (base 360 para o spread real).
  - IR regressivo sobre o rendimento, conforme prazo da aplicação.

Os valores são ESTIMATIVAS: a taxa CDI usada é a vigente hoje, projetada
para todo o período decorrido. O extrato do banco é sempre a fonte oficial.
"""

from __future__ import annotations

from datetime import date, timedelta

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


def aliquota_ir(dias_corridos: int) -> float:
    for limite, aliquota in TABELA_IR:
        if dias_corridos <= limite:
            return aliquota
    return 0.15


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

    valor_inicial = float(cdb["valor_inicial"])
    du = dias_uteis(aplicacao, referencia)
    dc = max((referencia - aplicacao).days, 0)
    indexador = cdb["indexador"]
    taxa = float(cdb["taxa"])

    aviso = None
    if indexador == "CDI":
        taxa_efetiva = cdi_anual_pct * (taxa / 100)
        fator = (1 + taxa_efetiva / 100) ** (du / 252)
    elif indexador == "PRE":
        taxa_efetiva = taxa
        fator = (1 + taxa / 100) ** (du / 252)
    else:  # IPCA+
        taxa_efetiva = taxa
        fator_juros = (1 + taxa / 100) ** (dc / 360)
        if ipca_fator is None:
            fator = fator_juros
            aviso = "IPCA indisponivel - considerado apenas o juro real."
        else:
            fator = ipca_fator * fator_juros

    valor_bruto = valor_inicial * fator
    rendimento_bruto = valor_bruto - valor_inicial
    ir_pct = aliquota_ir(dc)
    ir_valor = max(rendimento_bruto, 0) * ir_pct
    valor_liquido = valor_bruto - ir_valor

    dias_para_vencer = (vencimento - hoje).days

    return {
        "valor_inicial": round(valor_inicial, 2),
        "valor_bruto": round(valor_bruto, 2),
        "valor_liquido": round(valor_liquido, 2),
        "rendimento_bruto": round(rendimento_bruto, 2),
        "rendimento_liquido": round(valor_liquido - valor_inicial, 2),
        "rentabilidade_bruta_pct": round((fator - 1) * 100, 4),
        "rentabilidade_liquida_pct": round(
            (valor_liquido - valor_inicial) / valor_inicial * 100, 4
        ),
        "taxa_efetiva_aa_pct": round(taxa_efetiva, 4),
        "ir_aliquota_pct": round(ir_pct * 100, 2),
        "ir_valor": round(ir_valor, 2),
        "dias_corridos": dc,
        "dias_uteis": du,
        "dias_para_vencer": dias_para_vencer,
        "vencido": hoje >= vencimento,
        "aviso": aviso,
    }

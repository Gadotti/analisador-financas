"""Leitura da carteira gravada em JSON.

Quem cadastra, valida e grava posições é a aplicação Node — este módulo apenas
lê o arquivo para a análise. Por isso não há CRUD aqui: a validação mora num
lugar só, evitando duas regras divergentes para o mesmo arquivo.
"""

from __future__ import annotations

import copy
import json
from datetime import date

from .paths import portfolio_file

VERSAO = 2

TIPOS_VARIAVEL = ("fii", "acao")
TIPOS_RENDA_FIXA = ("cdb", "lci", "lca", "tesouro")
TIPOS = TIPOS_VARIAVEL + TIPOS_RENDA_FIXA

# Renda fixa emitida por banco: tem um emissor no cadastro e consome teto do
# FGC. O título público não entra aqui — quem responde por ele é o Tesouro
# Nacional, e o campo `banco` nem existe na posição.
TIPOS_BANCARIOS = ("cdb", "lci", "lca")

INDEXADORES_CDB = ("CDI", "PRE", "IPCA")
INDEXADORES_LETRA = ("CDI", "PRE", "IPCA")
INDEXADORES_TESOURO = ("SELIC", "PRE", "IPCA")

PAGAMENTOS_CDB = ("vencimento", "mensal")
PAGAMENTOS_LETRA = ("vencimento", "mensal", "semestral")
PAGAMENTOS_TESOURO = ("vencimento", "semestral")

# Sigla de cada papel bancário, para o nome de exibição de quem não tem nome.
SIGLA_BANCARIA = {"cdb": "CDB", "lci": "LCI", "lca": "LCA"}

EMISSOR_TESOURO = "Tesouro Nacional"

# Mensagem curta do Telegram. Cada bloco tem um interruptor (`ativo` — pode
# aparecer?) e um limiar (merece aparecer HOJE?). É o limiar que faz a mensagem
# variar de um dia para o outro sem que nada seja memorizado: na maioria dos
# dias, a maioria dos blocos não dispara. Ver `analise.relevancia`.
#
# `dias_semana` segue `date.weekday()`: 0 = segunda, 6 = domingo.
TELEGRAM_PADRAO = {
    "max_itens": 6,
    "so_se_relevante": False,
    "silencioso_sem_alerta": True,
    "variacao_dia": {"ativo": True, "limiar_pct": 0.5},
    "macro": {"ativo": True, "limiar_pp": 0.01},
    "movimento": {"ativo": True, "limiar_pct": 3.0, "peso_minimo_pct": 3.0, "max": 3},
    "calendario_rf": {"ativo": True, "marcos_dias": [30, 15, 7, 3, 1], "max": 2},
    "alertas": {"ativo": True, "severidade_minima": "atencao", "max": 3},
    "fatos_ia": {
        "ativo": True, "severidade_minima": "atencao", "peso_minimo_pct": 5.0, "max": 3,
    },
    "riscos_ia": {"ativo": True, "severidade_minima": "alerta", "max": 2},
    "indicadores": {
        "ativo": True, "p_vp_minimo": 0.85, "p_vp_maximo": 1.15, "dy_minimo_pct": 8.0,
    },
    "aprofundamento": {"ativo": True, "por_dia": 1},
    "resumo_ia": {"ativo": True, "dias_semana": [4]},
    "semanal": {"ativo": True, "dia_semana": 4},
}

CONFIG_PADRAO = {
    "max_fatos": 6,
    "max_oportunidades": 4,
    "max_execucoes": 30,
    "limite_fgc": 250000.0,
    "alerta_vencimento_dias": 60,
    "alerta_concentracao_pct": 25.0,
    "alerta_prejuizo_pct": 15.0,
    "telegram": TELEGRAM_PADRAO,
}


def config_padrao() -> dict:
    """Cópia independente dos padrões, com o bloco do Telegram já profundo.

    `dict(CONFIG_PADRAO)` é raso e devolveria o MESMO dicionário de
    `telegram` a todos os chamadores — escrever num deles mudaria o padrão do
    processo inteiro.
    """
    return {**CONFIG_PADRAO, "telegram": copy.deepcopy(TELEGRAM_PADRAO)}


def telegram_do_cadastro(bruto: dict | None) -> dict:
    """Bloco `telegram` gravado em disco sobre os padrões, um nível abaixo também.

    Um `update` raso trocaria o padrão inteiro pelo bloco parcial do arquivo, e
    um cadastro gravado antes de um limiar novo existir perderia esse limiar.
    """
    completo = copy.deepcopy(TELEGRAM_PADRAO)
    for chave, valor in (bruto or {}).items():
        if isinstance(completo.get(chave), dict) and isinstance(valor, dict):
            completo[chave].update(valor)
        else:
            completo[chave] = valor
    return completo


class CarteiraError(RuntimeError):
    """A carteira não pôde ser lida."""


def carteira_vazia() -> dict:
    return {
        "versao": VERSAO,
        "perfil": "",
        "posicoes": [],
        "config": config_padrao(),
    }


def load() -> dict:
    """Carrega a carteira. Devolve uma carteira vazia se o arquivo não existir."""
    arquivo = portfolio_file()
    if not arquivo.exists():
        return carteira_vazia()

    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except json.JSONDecodeError as exc:
        raise CarteiraError(f"Carteira corrompida em {arquivo}: {exc}") from None

    bruta = dados.get("config") or {}
    config = config_padrao()
    config.update(bruta)
    config["telegram"] = telegram_do_cadastro(bruta.get("telegram"))
    dados["config"] = config
    dados.setdefault("perfil", "")
    dados.setdefault("posicoes", [])
    return dados


def rotulo_taxa(titulo: dict) -> str:
    """Descrição legível da remuneração de um título de renda fixa."""
    taxa, idx = titulo["taxa"], titulo["indexador"]
    if idx == "CDI":
        return f"{taxa:g}% do CDI"
    if idx == "SELIC":
        return f"SELIC + {taxa:g}% a.a."
    if idx == "PRE":
        return f"{taxa:g}% a.a."
    return f"IPCA + {taxa:g}% a.a."


def emissor(titulo: dict) -> str:
    """Quem responde pelo título: o banco emissor ou o Tesouro Nacional."""
    if titulo["tipo"] == "tesouro":
        return EMISSOR_TESOURO
    return titulo.get("banco", "")


def paga_cupom(titulo: dict) -> bool:
    """O título devolve os juros no caminho em vez de acumular até o vencimento?"""
    return titulo.get("pagamento_juros") in ("mensal", "semestral")


def descricao(pos: dict) -> str:
    """Nome curto de exibição da posição."""
    if pos["tipo"] in TIPOS_VARIAVEL:
        return pos["ticker"]
    if pos.get("nome"):
        return pos["nome"]
    if pos["tipo"] == "tesouro":
        return "Tesouro Direto"
    return f"{SIGLA_BANCARIA[pos['tipo']]} {pos.get('banco', '')}".strip()


def tickers(carteira: dict) -> list[str]:
    """Tickers únicos de renda variável presentes na carteira."""
    vistos: list[str] = []
    for p in carteira["posicoes"]:
        if p["tipo"] in TIPOS_VARIAVEL and p["ticker"] not in vistos:
            vistos.append(p["ticker"])
    return vistos


def data_iso(valor) -> date | None:
    """Converte 'AAAA-MM-DD' em date, tolerando ausência."""
    if not valor:
        return None
    return date.fromisoformat(str(valor)[:10])

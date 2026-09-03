"""Leitura da carteira gravada em JSON.

Quem cadastra, valida e grava posições é a aplicação Node — este módulo apenas
lê o arquivo para a análise. Por isso não há CRUD aqui: a validação mora num
lugar só, evitando duas regras divergentes para o mesmo arquivo.
"""

from __future__ import annotations

import json
from datetime import date

from .paths import portfolio_file

VERSAO = 2

TIPOS_VARIAVEL = ("fii", "acao")
TIPOS_RENDA_FIXA = ("cdb",)
TIPOS = TIPOS_VARIAVEL + TIPOS_RENDA_FIXA

INDEXADORES = ("CDI", "PRE", "IPCA")
PAGAMENTOS_JUROS = ("vencimento", "mensal")

CONFIG_PADRAO = {
    "max_fatos": 6,
    "max_oportunidades": 4,
    "limite_fgc": 250000.0,
    "alerta_vencimento_dias": 60,
    "alerta_concentracao_pct": 25.0,
    "alerta_prejuizo_pct": 15.0,
}


class CarteiraError(RuntimeError):
    """A carteira não pôde ser lida."""


def carteira_vazia() -> dict:
    return {
        "versao": VERSAO,
        "perfil": "",
        "posicoes": [],
        "config": dict(CONFIG_PADRAO),
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

    config = dict(CONFIG_PADRAO)
    config.update(dados.get("config") or {})
    dados["config"] = config
    dados.setdefault("perfil", "")
    dados.setdefault("posicoes", [])
    return dados


def rotulo_taxa(cdb: dict) -> str:
    """Descrição legível da remuneração de um CDB."""
    taxa, idx = cdb["taxa"], cdb["indexador"]
    if idx == "CDI":
        return f"{taxa:g}% do CDI"
    if idx == "PRE":
        return f"{taxa:g}% a.a."
    return f"IPCA + {taxa:g}% a.a."


def paga_juros_mensais(cdb: dict) -> bool:
    """O CDB devolve os juros todo mês em vez de acumular até o vencimento?"""
    return cdb.get("pagamento_juros") == "mensal"


def descricao(pos: dict) -> str:
    """Nome curto de exibição da posição."""
    if pos["tipo"] in TIPOS_VARIAVEL:
        return pos["ticker"]
    return pos.get("nome") or f"CDB {pos.get('banco', '')}"


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

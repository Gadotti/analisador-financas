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
TIPOS_RENDA_FIXA = ("cdb", "tesouro")
TIPOS = TIPOS_VARIAVEL + TIPOS_RENDA_FIXA

INDEXADORES_CDB = ("CDI", "PRE", "IPCA")
INDEXADORES_TESOURO = ("SELIC", "PRE", "IPCA")

PAGAMENTOS_CDB = ("vencimento", "mensal")
PAGAMENTOS_TESOURO = ("vencimento", "semestral")

EMISSOR_TESOURO = "Tesouro Nacional"

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
    return "Tesouro Direto" if pos["tipo"] == "tesouro" else f"CDB {pos.get('banco', '')}"


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

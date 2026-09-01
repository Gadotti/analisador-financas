"""Persistência e validação da carteira em arquivo JSON.

Tipos de posição suportados:
  - "fii" / "acao": ticker, quantidade, preço médio
  - "cdb"         : banco, valor inicial, indexador, taxa, datas
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from typing import Any

from .paths import PORTFOLIO_FILE

VERSAO = 2

TIPOS_VARIAVEL = ("fii", "acao")
TIPOS_RENDA_FIXA = ("cdb",)
TIPOS = TIPOS_VARIAVEL + TIPOS_RENDA_FIXA

INDEXADORES = ("CDI", "PRE", "IPCA")

CONFIG_PADRAO = {
    "max_fatos": 6,
    "max_oportunidades": 4,
    "limite_fgc": 250000.0,
    "alerta_vencimento_dias": 60,
    "alerta_concentracao_pct": 25.0,
    "alerta_prejuizo_pct": 15.0,
}


class ValidacaoError(ValueError):
    """Erro de validação de uma posição da carteira."""


# ─────────────────────────────────────────────
# Leitura / escrita
# ─────────────────────────────────────────────

def carteira_vazia() -> dict:
    return {
        "versao": VERSAO,
        "perfil": "",
        "posicoes": [],
        "config": dict(CONFIG_PADRAO),
    }


def load() -> dict:
    """Carrega a carteira, migrando formatos antigos quando necessário."""
    if not PORTFOLIO_FILE.exists():
        carteira = carteira_vazia()
        save(carteira)
        return carteira

    with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
        dados = json.load(f)

    if dados.get("versao") != VERSAO:
        dados = _migrar(dados)
        save(dados)

    config = dict(CONFIG_PADRAO)
    config.update(dados.get("config") or {})
    dados["config"] = config
    dados.setdefault("perfil", "")
    dados.setdefault("posicoes", [])
    return dados


def save(carteira: dict) -> None:
    carteira["versao"] = VERSAO
    carteira["atualizado_em"] = datetime.now().isoformat(timespec="seconds")
    tmp = PORTFOLIO_FILE.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(carteira, f, ensure_ascii=False, indent=2)
    tmp.replace(PORTFOLIO_FILE)


def _migrar(antigo: dict) -> dict:
    """Converte o formato v1 (lista de tickers de FII) para o formato atual."""
    nova = carteira_vazia()
    nova["perfil"] = antigo.get("profile") or antigo.get("perfil") or ""

    for pos in antigo.get("posicoes", []):
        try:
            nova["posicoes"].append(normalizar(pos))
        except ValidacaoError:
            continue

    for ticker in antigo.get("tickers", []):
        nova["posicoes"].append(
            normalizar({
                "tipo": "fii",
                "ticker": ticker,
                "quantidade": 0,
                "preco_medio": 0,
                "observacao": "Migrado do formato antigo - informe quantidade e preco medio.",
            })
        )

    for chave in ("max_fatos", "max_oportunidades"):
        if chave in antigo:
            nova["config"][chave] = antigo[chave]

    return nova


# ─────────────────────────────────────────────
# Validação / normalização
# ─────────────────────────────────────────────

def _num(valor: Any, campo: str, *, minimo: float | None = None) -> float:
    if valor is None or valor == "":
        raise ValidacaoError(f"Campo '{campo}' e obrigatorio.")
    try:
        n = float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        raise ValidacaoError(f"Campo '{campo}' deve ser numerico.") from None
    if minimo is not None and n < minimo:
        raise ValidacaoError(f"Campo '{campo}' deve ser >= {minimo}.")
    return n


def _data(valor: Any, campo: str, *, obrigatorio: bool = True) -> str | None:
    if not valor:
        if obrigatorio:
            raise ValidacaoError(f"Campo '{campo}' e obrigatorio (formato AAAA-MM-DD).")
        return None
    try:
        return date.fromisoformat(str(valor)[:10]).isoformat()
    except ValueError:
        raise ValidacaoError(f"Campo '{campo}' invalido - use AAAA-MM-DD.") from None


def _texto(valor: Any, campo: str, *, obrigatorio: bool = True) -> str:
    txt = (str(valor).strip() if valor is not None else "")
    if obrigatorio and not txt:
        raise ValidacaoError(f"Campo '{campo}' e obrigatorio.")
    return txt


def normalizar(pos: dict) -> dict:
    """Valida e normaliza uma posição, devolvendo um dict pronto para gravar."""
    tipo = _texto(pos.get("tipo"), "tipo").lower()
    if tipo not in TIPOS:
        raise ValidacaoError(f"Tipo invalido: '{tipo}'. Use: {', '.join(TIPOS)}.")

    base = {
        "id": pos.get("id") or uuid.uuid4().hex[:12],
        "tipo": tipo,
        "observacao": _texto(pos.get("observacao"), "observacao", obrigatorio=False),
    }

    if tipo in TIPOS_VARIAVEL:
        base.update({
            "ticker": _texto(pos.get("ticker"), "ticker").upper().replace(".SA", ""),
            "quantidade": _num(pos.get("quantidade"), "quantidade", minimo=0),
            "preco_medio": _num(pos.get("preco_medio"), "preco_medio", minimo=0),
            "data_compra": _data(pos.get("data_compra"), "data_compra", obrigatorio=False),
        })
        return base

    # CDB
    indexador = _texto(pos.get("indexador") or "CDI", "indexador").upper()
    if indexador not in INDEXADORES:
        raise ValidacaoError(
            f"Indexador invalido: '{indexador}'. Use: {', '.join(INDEXADORES)}."
        )

    data_aplicacao = _data(pos.get("data_aplicacao"), "data_aplicacao")
    data_vencimento = _data(pos.get("data_vencimento"), "data_vencimento")
    if data_vencimento < data_aplicacao:
        raise ValidacaoError("Data de vencimento anterior a data de aplicacao.")

    base.update({
        "banco": _texto(pos.get("banco"), "banco"),
        "nome": _texto(pos.get("nome"), "nome", obrigatorio=False),
        "valor_inicial": _num(pos.get("valor_inicial"), "valor_inicial", minimo=0.01),
        "indexador": indexador,
        "taxa": _num(pos.get("taxa"), "taxa", minimo=0),
        "data_aplicacao": data_aplicacao,
        "data_vencimento": data_vencimento,
        "liquidez_diaria": bool(pos.get("liquidez_diaria", False)),
    })
    if not base["nome"]:
        base["nome"] = f"CDB {base['banco']} {rotulo_taxa(base)}"
    return base


def rotulo_taxa(cdb: dict) -> str:
    """Descrição legível da remuneração de um CDB."""
    taxa, idx = cdb["taxa"], cdb["indexador"]
    if idx == "CDI":
        return f"{taxa:g}% do CDI"
    if idx == "PRE":
        return f"{taxa:g}% a.a."
    return f"IPCA + {taxa:g}% a.a."


def descricao(pos: dict) -> str:
    """Nome curto de exibição da posição."""
    if pos["tipo"] in TIPOS_VARIAVEL:
        return pos["ticker"]
    return pos.get("nome") or f"CDB {pos.get('banco', '')}"


# ─────────────────────────────────────────────
# CRUD
# ─────────────────────────────────────────────

def adicionar(pos: dict) -> dict:
    carteira = load()
    nova = normalizar({**pos, "id": None})
    carteira["posicoes"].append(nova)
    save(carteira)
    return nova


def atualizar(pos_id: str, pos: dict) -> dict:
    carteira = load()
    for i, atual in enumerate(carteira["posicoes"]):
        if atual["id"] == pos_id:
            nova = normalizar({**pos, "id": pos_id})
            carteira["posicoes"][i] = nova
            save(carteira)
            return nova
    raise ValidacaoError(f"Posicao '{pos_id}' nao encontrada.")


def remover(pos_id: str) -> None:
    carteira = load()
    restantes = [p for p in carteira["posicoes"] if p["id"] != pos_id]
    if len(restantes) == len(carteira["posicoes"]):
        raise ValidacaoError(f"Posicao '{pos_id}' nao encontrada.")
    carteira["posicoes"] = restantes
    save(carteira)


def atualizar_config(patch: dict) -> dict:
    carteira = load()
    if "perfil" in patch:
        carteira["perfil"] = _texto(patch["perfil"], "perfil", obrigatorio=False)
    for chave, valor in (patch.get("config") or {}).items():
        if chave in CONFIG_PADRAO:
            carteira["config"][chave] = _num(valor, chave, minimo=0)
    save(carteira)
    return carteira


def tickers(carteira: dict) -> list[str]:
    """Tickers únicos de renda variável presentes na carteira."""
    vistos: list[str] = []
    for p in carteira["posicoes"]:
        if p["tipo"] in TIPOS_VARIAVEL and p["ticker"] not in vistos:
            vistos.append(p["ticker"])
    return vistos

"""Cotações de renda variável e indicadores macro.

Fontes (todas públicas, sem cadastro obrigatório):
  - Cotações B3 .............. Yahoo Finance (chart API); fallback brapi.dev
  - CDI / Selic / IPCA ....... Banco Central, séries SGS

Todas as respostas passam por um cache em disco com TTL para evitar
consultas repetidas dentro do mesmo dia.
"""

from __future__ import annotations

import json
import os
import time
from datetime import date, datetime

import requests

from .paths import cache_file, garantir_diretorios

TIMEOUT = 15
UA = {"User-Agent": "Mozilla/5.0 (compatible; PortfolioAnalyzer/1.0)"}

TTL_COTACAO = 15 * 60      # 15 minutos
TTL_INDICADOR = 12 * 3600  # 12 horas

# Séries do SGS/BCB
SGS_CDI_ANUAL = 4389   # Taxa CDI acumulada anualizada (% a.a.)
SGS_SELIC_META = 432   # Meta Selic definida pelo Copom (% a.a.)
SGS_IPCA_MES = 433     # IPCA - variação mensal (%)


# ─────────────────────────────────────────────
# Cache em disco
# ─────────────────────────────────────────────

def _cache_ler() -> dict:
    try:
        with open(cache_file(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _cache_gravar(cache: dict) -> None:
    try:
        garantir_diretorios()
        with open(cache_file(), "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    except OSError:
        pass


def _cache_get(chave: str, ttl: int):
    entrada = _cache_ler().get(chave)
    if entrada and (time.time() - entrada.get("ts", 0)) < ttl:
        return entrada.get("valor")
    return None


def _cache_set(chave: str, valor) -> None:
    cache = _cache_ler()
    cache[chave] = {"ts": time.time(), "valor": valor}
    _cache_gravar(cache)


def limpar_cache() -> None:
    _cache_gravar({})


# ─────────────────────────────────────────────
# Cotações
# ─────────────────────────────────────────────

def _yahoo(ticker: str) -> dict | None:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}.SA"
    resp = requests.get(
        url,
        params={"interval": "1d", "range": "5d"},
        headers=UA,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    resultado = (resp.json().get("chart") or {}).get("result") or []
    if not resultado:
        return None
    meta = resultado[0].get("meta") or {}
    preco = meta.get("regularMarketPrice")
    if preco is None:
        return None
    anterior = meta.get("chartPreviousClose") or meta.get("previousClose") or preco
    return {
        "ticker": ticker,
        "preco": float(preco),
        "fechamento_anterior": float(anterior),
        "variacao_dia_pct": _pct(float(preco) - float(anterior), float(anterior)),
        "nome": meta.get("longName") or meta.get("shortName") or ticker,
        "moeda": meta.get("currency", "BRL"),
        "fonte": "yahoo",
    }


def _brapi(ticker: str) -> dict | None:
    token = os.getenv("BRAPI_TOKEN")
    params = {"token": token} if token else {}
    resp = requests.get(
        f"https://brapi.dev/api/quote/{ticker}",
        params=params,
        headers=UA,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    itens = resp.json().get("results") or []
    if not itens:
        return None
    it = itens[0]
    preco = it.get("regularMarketPrice")
    if preco is None:
        return None
    return {
        "ticker": ticker,
        "preco": float(preco),
        "fechamento_anterior": float(it.get("regularMarketPreviousClose") or preco),
        "variacao_dia_pct": float(it.get("regularMarketChangePercent") or 0.0),
        "nome": it.get("longName") or it.get("shortName") or ticker,
        "moeda": it.get("currency", "BRL"),
        "fonte": "brapi",
    }


def cotacao(ticker: str, *, usar_cache: bool = True) -> dict:
    """Cotação de um ativo da B3.

    Retorna sempre um dict; em caso de falha inclui a chave 'erro' e
    'preco' = None, para que a análise continue sem quebrar.
    """
    ticker = ticker.upper().strip()
    chave = f"cotacao:{ticker}"

    if usar_cache:
        em_cache = _cache_get(chave, TTL_COTACAO)
        if em_cache:
            return {**em_cache, "do_cache": True}

    erros = []
    for provedor in (_yahoo, _brapi):
        try:
            dados = provedor(ticker)
            if dados:
                _cache_set(chave, dados)
                return {**dados, "do_cache": False}
            erros.append(f"{provedor.__name__}: sem dados")
        except Exception as exc:  # rede, HTTP, parsing
            erros.append(f"{provedor.__name__}: {exc}")

    return {
        "ticker": ticker,
        "preco": None,
        "fechamento_anterior": None,
        "variacao_dia_pct": None,
        "nome": ticker,
        "fonte": None,
        "erro": " | ".join(erros),
    }


def cotacoes(tickers: list[str], *, usar_cache: bool = True) -> dict[str, dict]:
    return {t: cotacao(t, usar_cache=usar_cache) for t in tickers}


# ─────────────────────────────────────────────
# Indicadores (Banco Central)
# ─────────────────────────────────────────────

def _sgs(serie: int, *, ultimos: int = 1, inicio: date | None = None) -> list[dict]:
    if inicio:
        url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados"
        params = {
            "formato": "json",
            "dataInicial": inicio.strftime("%d/%m/%Y"),
            "dataFinal": date.today().strftime("%d/%m/%Y"),
        }
    else:
        url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados/ultimos/{ultimos}"
        params = {"formato": "json"}
    resp = requests.get(url, params=params, headers=UA, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _ultimo_valor(serie: int, chave: str, padrao: float) -> dict:
    em_cache = _cache_get(chave, TTL_INDICADOR)
    if em_cache:
        return em_cache
    try:
        dados = _sgs(serie, ultimos=1)
        valor = {
            "valor": float(dados[-1]["valor"].replace(",", ".")),
            "data": dados[-1]["data"],
            "fonte": f"BCB/SGS {serie}",
        }
        _cache_set(chave, valor)
        return valor
    except Exception as exc:
        return {"valor": padrao, "data": None, "fonte": "padrao", "erro": str(exc)}


def cdi_anual() -> dict:
    """Taxa CDI acumulada anualizada, em % a.a."""
    return _ultimo_valor(SGS_CDI_ANUAL, "cdi_anual", 14.9)


def selic_meta() -> dict:
    """Meta Selic vigente, em % a.a."""
    return _ultimo_valor(SGS_SELIC_META, "selic_meta", 15.0)


def ipca_acumulado(desde: date) -> dict:
    """IPCA acumulado (fator) entre `desde` e hoje."""
    chave = f"ipca_acum:{desde.isoformat()}"
    em_cache = _cache_get(chave, TTL_INDICADOR)
    if em_cache:
        return em_cache
    try:
        dados = _sgs(SGS_IPCA_MES, inicio=desde)
        fator = 1.0
        for item in dados:
            fator *= 1 + float(item["valor"].replace(",", ".")) / 100
        valor = {
            "fator": fator,
            "variacao_pct": (fator - 1) * 100,
            "meses": len(dados),
            "fonte": f"BCB/SGS {SGS_IPCA_MES}",
        }
        _cache_set(chave, valor)
        return valor
    except Exception as exc:
        return {"fator": None, "variacao_pct": None, "meses": 0, "erro": str(exc)}


def ipca_12m() -> dict:
    """IPCA acumulado nos últimos 12 meses, em %."""
    chave = "ipca_12m"
    em_cache = _cache_get(chave, TTL_INDICADOR)
    if em_cache:
        return em_cache
    try:
        dados = _sgs(SGS_IPCA_MES, ultimos=12)
        fator = 1.0
        for item in dados:
            fator *= 1 + float(item["valor"].replace(",", ".")) / 100
        valor = {"valor": (fator - 1) * 100, "fonte": f"BCB/SGS {SGS_IPCA_MES}"}
        _cache_set(chave, valor)
        return valor
    except Exception as exc:
        return {"valor": None, "fonte": None, "erro": str(exc)}


def indices_mercado() -> dict:
    """Ibovespa e IFIX (quando disponível na fonte)."""
    chave = "indices_mercado"
    em_cache = _cache_get(chave, TTL_COTACAO)
    if em_cache:
        return em_cache

    saida = {}
    for nome, simbolo in (("ibovespa", "^BVSP"), ("ifix", "^IFIX")):
        try:
            resp = requests.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}",
                params={"interval": "1d", "range": "5d"},
                headers=UA,
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            meta = ((resp.json().get("chart") or {}).get("result") or [{}])[0].get("meta") or {}
            preco = meta.get("regularMarketPrice")
            if preco is None:
                continue
            anterior = meta.get("chartPreviousClose") or preco
            saida[nome] = {
                "valor": float(preco),
                "variacao_dia_pct": _pct(float(preco) - float(anterior), float(anterior)),
            }
        except Exception:
            continue

    _cache_set(chave, saida)
    return saida


def cenario_macro() -> dict:
    """Fotografia dos indicadores macro usados na análise."""
    return {
        "cdi_anual_pct": cdi_anual(),
        "selic_meta_pct": selic_meta(),
        "ipca_12m_pct": ipca_12m(),
        "indices": indices_mercado(),
        "consultado_em": datetime.now().isoformat(timespec="seconds"),
    }


# ─────────────────────────────────────────────
# Utilitário
# ─────────────────────────────────────────────

def _pct(delta: float, base: float) -> float | None:
    return (delta / base * 100) if base else None

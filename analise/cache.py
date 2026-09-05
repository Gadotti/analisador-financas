"""Cache em disco com TTL, compartilhado pelos coletores de dados externos.

Um arquivo só (`data/cache.json`) atende `market` e `tesouro_direto`, para que
uma execução não repita a mesma consulta duas vezes. Falha de escrita nunca
interrompe a análise: o cache é uma otimização, não uma fonte.

`SEM_EXPIRAR` marca o dado que não muda mais — a taxa de um título numa data
já fechada, por exemplo. Ele fica no arquivo até alguém limpar o cache.
"""

from __future__ import annotations

import json
import time

from .paths import cache_file, garantir_diretorios

SEM_EXPIRAR = float("inf")


def ler() -> dict:
    try:
        with open(cache_file(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def gravar(cache: dict) -> None:
    try:
        garantir_diretorios()
        with open(cache_file(), "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    except OSError:
        pass


def obter(chave: str, ttl: float):
    """Valor ainda válido para `chave`, ou None se ausente ou vencido."""
    entrada = ler().get(chave)
    if entrada and (time.time() - entrada.get("ts", 0)) < ttl:
        return entrada.get("valor")
    return None


def definir(chave: str, valor) -> None:
    cache = ler()
    cache[chave] = {"ts": time.time(), "valor": valor}
    gravar(cache)


def definir_varios(itens: dict) -> None:
    """Grava várias chaves numa passada só — uma leitura e uma escrita."""
    if not itens:
        return
    cache = ler()
    agora = time.time()
    for chave, valor in itens.items():
        cache[chave] = {"ts": agora, "valor": valor}
    gravar(cache)


def limpar() -> None:
    gravar({})

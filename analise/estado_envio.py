"""Estado de deduplicação do Telegram: o que já foi enviado, sem virar histórico.

Guarda só o hash do texto de cada alerta, risco ou fato que já saiu numa
mensagem, por bloco (`alertas`, `riscos_ia`, `fatos_ia`). Não é um log: a cada
envio bem-sucedido `podar` descarta o hash de tudo o que não está mais na
leitura de hoje — um achado que muda de texto, ou desaparece, perde o registro
e volta a valer como novo se reaparecer.

`gatilhos` calcula o hash na origem — sobre o objeto cru da IA ou do cálculo,
antes de qualquer decoração de título — e o carrega no item como
`chave_envio`; é esse valor que `relevancia` compara contra o estado para não
repetir um achado inalterado, e que `scripts/analisar.py` grava de volta depois
de um envio de verdade. `runner` usa as mesmas funções de hash sobre os
objetos crus para anotar `enviado_telegram` na tela, mesmo quando esta
execução não chega a falar com o Telegram.
"""

from __future__ import annotations

import hashlib
import json

from .paths import garantir_diretorios, telegram_enviados_file

BLOCOS = ("alertas", "riscos_ia", "fatos_ia")


def _hash(*partes: str) -> str:
    return hashlib.sha256("|".join(partes).encode("utf-8")).hexdigest()[:16]


def hash_alerta(alerta: dict) -> str:
    return _hash(alerta["titulo"], alerta["descricao"])


def hash_risco(risco: dict) -> str:
    return _hash(risco["titulo"], risco["descricao"])


def hash_fato(fato: dict) -> str:
    return _hash(fato.get("ativo", ""), fato["titulo"], fato["descricao"])


HASH_DO_BLOCO = {"alertas": hash_alerta, "riscos_ia": hash_risco, "fatos_ia": hash_fato}


def ler() -> dict:
    try:
        with open(telegram_enviados_file(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def gravar(estado: dict) -> None:
    try:
        garantir_diretorios()
        with open(telegram_enviados_file(), "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False)
    except OSError:
        pass


def marcar(itens: list[dict], bloco: str, estado: dict) -> list[dict]:
    """Os mesmos itens crus, cada um com `enviado_telegram` anotado.

    Função pura: só compara contra o `estado` recebido, nunca lê o disco.
    """
    hash_de = HASH_DO_BLOCO[bloco]
    enviados = set(estado.get(bloco) or [])
    return [{**item, "enviado_telegram": hash_de(item) in enviados} for item in itens]


def podar(estado: dict, itens_atuais: dict[str, list[dict]]) -> dict:
    """Só sobrevive o hash de um achado que ainda está na leitura de hoje.

    É o que impede o arquivo de virar um histórico: sem isso, um risco ou fato
    que já saiu de cena continuaria marcado como "enviado" para sempre.
    """
    podado = {}
    for bloco in BLOCOS:
        hash_de = HASH_DO_BLOCO[bloco]
        correntes = {hash_de(item) for item in itens_atuais.get(bloco) or []}
        podado[bloco] = sorted(correntes & set(estado.get(bloco) or []))
    return podado


def registrar_envio(estado: dict, chaves_por_bloco: dict[str, list[str]]) -> dict:
    """Acrescenta ao estado a chave de cada item que acabou de ser enviado."""
    novo = {bloco: list(estado.get(bloco) or []) for bloco in BLOCOS}
    for bloco, chaves in chaves_por_bloco.items():
        hashes = set(novo.get(bloco) or [])
        hashes.update(chave for chave in chaves if chave)
        novo[bloco] = sorted(hashes)
    return novo

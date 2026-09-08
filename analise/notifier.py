"""Envio de notificações via bot do Telegram (opcional)."""

from __future__ import annotations

import os

import requests

TIMEOUT = 30


def configurado() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def _conferir(resp, acao: str) -> dict:
    """Devolve o corpo da resposta ou levanta o motivo que a API informou.

    Não use `raise_for_status()` aqui: a mensagem dele traz a URL chamada, e o
    token do bot vai na URL — ele acabaria no log e na tela. O `description` do
    Telegram é o que diz de fato o que houve ("chat not found",
    "can't parse entities").
    """
    if resp.ok:
        return resp.json()

    try:
        motivo = resp.json().get("description") or resp.text
    except ValueError:
        motivo = resp.text
    raise RuntimeError(f"Telegram recusou {acao} (HTTP {resp.status_code}): {motivo}")


def enviar(mensagem: str) -> dict:
    """Envia uma mensagem HTML ao chat configurado."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID precisam estar configurados no .env."
        )

    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": mensagem,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=TIMEOUT,
    )
    return _conferir(resp, "o envio da mensagem")


def testar() -> str:
    """Valida o token e envia uma mensagem de teste. Retorna o nome do bot."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN não configurado.")

    resp = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=TIMEOUT)
    nome = _conferir(resp, "a validação do token")["result"].get("first_name", "Bot")

    enviar(
        "🤖 <b>Portfolio Analyzer conectado</b>\n"
        "Os relatórios da sua carteira serão enviados aqui."
    )
    return nome

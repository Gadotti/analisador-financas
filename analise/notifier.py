"""Envio de notificações via bot do Telegram (opcional)."""

from __future__ import annotations

import os

import requests

TIMEOUT = 30


def configurado() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


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
    resp.raise_for_status()
    return resp.json()


def testar() -> str:
    """Valida o token e envia uma mensagem de teste. Retorna o nome do bot."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN não configurado.")

    resp = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=TIMEOUT)
    resp.raise_for_status()
    nome = resp.json()["result"].get("first_name", "Bot")

    enviar(
        "🤖 <b>Portfolio Analyzer conectado</b>\n"
        "Os relatórios da sua carteira serão enviados aqui."
    )
    return nome

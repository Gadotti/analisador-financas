"""Envio ao Telegram: o que a API recusou tem de chegar ao usuário, sem o token."""

import pytest

from analise import notifier

TOKEN = "123456789:TESTE-FAKE-TOKEN-NAO-USAR-EM-PRODUCAO"


class RespostaTelegram:
    """Imita a resposta do requests para a API do Telegram."""

    def __init__(self, corpo, status=200, texto=""):
        self._corpo = corpo
        self.text = texto or str(corpo)
        self.status_code = status
        self.ok = status < 400

    def json(self):
        if self._corpo is None:
            raise ValueError("resposta sem JSON")
        return self._corpo


@pytest.fixture
def telegram(monkeypatch):
    """Credenciais de teste e um requests.post que devolve o que o teste quiser."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "8949194659")

    enviadas: list = []
    caixa = {"resposta": RespostaTelegram({"ok": True, "result": {"message_id": 1}})}

    def falso_post(url, json=None, timeout=None):
        enviadas.append({"url": url, "corpo": json})
        return caixa["resposta"]

    monkeypatch.setattr(notifier.requests, "post", falso_post)
    return type("T", (), {"enviadas": enviadas, "caixa": caixa})()


def test_enviar_devolve_o_corpo_quando_aceito(telegram):
    assert notifier.enviar("olá")["ok"] is True
    assert telegram.enviadas[0]["corpo"]["parse_mode"] == "HTML"


def test_envio_sempre_toca_o_aparelho(telegram):
    """Nenhuma mensagem deste sistema deve chegar silenciosa."""
    notifier.enviar("olá")

    assert telegram.enviadas[0]["corpo"]["disable_notification"] is False


def test_erro_traz_a_descricao_da_api(telegram):
    telegram.caixa["resposta"] = RespostaTelegram(
        {"ok": False, "error_code": 400, "description": "Bad Request: chat not found"},
        status=400,
    )

    with pytest.raises(RuntimeError, match="chat not found"):
        notifier.enviar("olá")


def test_erro_nunca_expoe_o_token_do_bot(telegram):
    """A URL chamada leva o token; `raise_for_status` a colocaria na mensagem."""
    telegram.caixa["resposta"] = RespostaTelegram(
        {"ok": False, "description": "Bad Request: can't parse entities"}, status=400
    )

    with pytest.raises(RuntimeError) as erro:
        notifier.enviar("<i>aberta")

    assert TOKEN not in str(erro.value)
    assert "api.telegram.org" not in str(erro.value)


def test_erro_sem_json_usa_o_texto_da_resposta(telegram):
    telegram.caixa["resposta"] = RespostaTelegram(None, status=502, texto="Bad Gateway")

    with pytest.raises(RuntimeError, match="Bad Gateway"):
        notifier.enviar("olá")


def test_enviar_sem_configuracao_explica_o_que_falta(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    assert notifier.configurado() is False
    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        notifier.enviar("olá")

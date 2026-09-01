"""Contrato da chamada à API da Anthropic e montagem do prompt."""

import copy
import json
from types import SimpleNamespace

import pytest

from analise import ai_insights as ia

CONFIG = {"max_fatos": 5, "max_oportunidades": 3}


class ClienteFalso:
    """Registra os parâmetros recebidos em cada canal (beta e normal)."""

    def __init__(self, resposta=None, falhar_com=None):
        self.resposta = resposta
        self.falhar_com = falhar_com
        self.chamadas = {"beta": [], "normal": []}
        self.beta = SimpleNamespace(
            messages=SimpleNamespace(create=lambda **kw: self._responder(kw, "beta"))
        )
        self.messages = SimpleNamespace(create=lambda **kw: self._responder(kw, "normal"))

    def _responder(self, parametros, canal):
        self.chamadas[canal].append(parametros)
        if self.falhar_com:
            raise self.falhar_com
        return self.resposta


def resposta_valida(dados):
    return SimpleNamespace(
        model="claude-opus-5",
        stop_reason="end_turn",
        content=[
            SimpleNamespace(type="text", text="vou pesquisar"),
            SimpleNamespace(type="text", text=json.dumps(dados)),
        ],
        usage=SimpleNamespace(
            input_tokens=1200,
            output_tokens=3400,
            server_tool_use=SimpleNamespace(web_search_requests=6),
        ),
    )


@pytest.fixture
def com_chave(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-teste")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-5")
    monkeypatch.setenv("ANTHROPIC_EFFORT", "medium")


# ─────────────────────────────────────────────
# Configuração
# ─────────────────────────────────────────────


def test_indisponivel_sem_chave(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    ok, motivo = ia.disponivel()

    assert ok is False
    assert "ANTHROPIC_API_KEY" in motivo


def test_disponivel_com_chave(com_chave):
    assert ia.disponivel() == (True, "")


def test_modelo_e_effort_padrao(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    monkeypatch.delenv("ANTHROPIC_EFFORT", raising=False)

    assert ia.modelo() == "claude-opus-5"
    assert ia.effort() == "medium"


def test_modelo_e_effort_do_ambiente(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-5")
    monkeypatch.setenv("ANTHROPIC_EFFORT", "high")

    assert ia.modelo() == "claude-sonnet-5"
    assert ia.effort() == "high"


@pytest.mark.parametrize(
    "modelo,esperado",
    [
        ("claude-opus-5", True),
        ("claude-fable-5", True),
        ("claude-sonnet-5", False),
        ("claude-haiku-4-5", False),
    ],
)
def test_familias_com_fallback(modelo, esperado):
    assert ia.suporta_fallback(modelo) is esperado


# ─────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────


def test_prompt_descreve_posicoes_perfil_alertas_e_tarefa(snapshot_exemplo):
    prompt = ia.montar_prompt(snapshot_exemplo, CONFIG)

    assert "Total investido: R$ 20,000.00" in prompt
    assert "Valor atual: R$ 22,000.00 (+10.00%)" in prompt
    assert "[FII] MXRF11: 1000 cotas" in prompt
    assert "[CDB] Inter — 110% do CDI" in prompt
    assert "vence em 490 dias" in prompt
    assert "Renda mensal com risco moderado" in prompt
    assert "[atencao] Concentracao em MXRF11" in prompt
    assert "CDI: 14.9% a.a." in prompt
    assert "1 ativos de renda variável: MXRF11" in prompt
    assert "no máximo 5 fatos recentes" in prompt
    assert "no máximo 3 pontos de observação" in prompt


def test_prompt_sem_perfil_nem_alertas(snapshot_exemplo):
    snapshot = copy.deepcopy(snapshot_exemplo)
    snapshot["perfil"] = ""
    snapshot["alertas"] = []

    prompt = ia.montar_prompt(snapshot, CONFIG)

    assert "Não informado." in prompt
    assert "Nenhum alerta automático" in prompt


def test_prompt_marca_cdb_vencido(snapshot_exemplo):
    snapshot = copy.deepcopy(snapshot_exemplo)
    snapshot["posicoes"][1]["vencido"] = True

    assert "VENCIDO" in ia.montar_prompt(snapshot, CONFIG)


# ─────────────────────────────────────────────
# Extração do JSON
# ─────────────────────────────────────────────


def bloco(texto, tipo="text"):
    return SimpleNamespace(type=tipo, text=texto)


def test_extrai_o_ultimo_bloco_de_texto():
    blocos = [bloco("pesquisando..."), bloco('{"a": 1}')]
    assert ia.extrair_json(blocos) == {"a": 1}


def test_remove_cercas_de_codigo():
    assert ia.extrair_json([bloco('```json\n{"a": 2}\n```')]) == {"a": 2}


def test_ignora_blocos_que_nao_sao_texto():
    blocos = [
        SimpleNamespace(type="web_search_tool_result", text=""),
        bloco("   "),
        bloco('{"a": 3}'),
    ]
    assert ia.extrair_json(blocos) == {"a": 3}


def test_erra_sem_texto_ou_com_json_invalido():
    with pytest.raises(ia.IAIndisponivel, match="nenhum bloco de texto"):
        ia.extrair_json([])
    with pytest.raises(ia.IAIndisponivel, match="JSON válido"):
        ia.extrair_json([bloco("oi")])


# ─────────────────────────────────────────────
# Chamada
# ─────────────────────────────────────────────


def test_recusa_sem_chave(snapshot_exemplo, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(ia.IAIndisponivel):
        ia.analisar(snapshot_exemplo, CONFIG)


def test_usa_o_canal_beta_com_fallback(snapshot_exemplo, com_chave):
    cliente = ClienteFalso(resposta_valida({"resumo": "ok"}))

    dados = ia.analisar(snapshot_exemplo, CONFIG, criar_cliente=lambda: cliente)

    assert len(cliente.chamadas["beta"]) == 1
    assert cliente.chamadas["normal"] == []

    parametros = cliente.chamadas["beta"][0]
    assert parametros["model"] == "claude-opus-5"
    assert parametros["fallbacks"] == "default"
    assert parametros["betas"] == ["server-side-fallback-2026-07-01"]
    assert parametros["output_config"]["effort"] == "medium"
    assert parametros["output_config"]["format"]["type"] == "json_schema"
    assert parametros["output_config"]["format"]["schema"] is ia.SCHEMA
    assert parametros["tools"] == [{"type": "web_search_20260209", "name": "web_search"}]
    assert parametros["max_tokens"] == ia.MAX_TOKENS
    assert parametros["messages"][0]["role"] == "user"

    assert dados["resumo"] == "ok"
    assert dados["_meta"]["modelo"] == "claude-opus-5"
    assert dados["_meta"]["effort"] == "medium"
    assert dados["_meta"]["tokens_entrada"] == 1200
    assert dados["_meta"]["buscas_web"] == 6


def test_usa_o_canal_normal_sem_fallback(snapshot_exemplo, com_chave, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-5")
    cliente = ClienteFalso(resposta_valida({"resumo": "ok"}))

    ia.analisar(snapshot_exemplo, CONFIG, criar_cliente=lambda: cliente)

    assert len(cliente.chamadas["normal"]) == 1
    assert cliente.chamadas["beta"] == []
    assert "fallbacks" not in cliente.chamadas["normal"][0]


def test_recusa_do_modelo_vira_ia_indisponivel(snapshot_exemplo, com_chave):
    recusa = SimpleNamespace(
        model="claude-opus-5",
        stop_reason="refusal",
        stop_details=SimpleNamespace(category="cyber"),
        content=[],
    )

    with pytest.raises(ia.IAIndisponivel, match="recusou responder.*cyber"):
        ia.analisar(snapshot_exemplo, CONFIG, criar_cliente=lambda: ClienteFalso(recusa))


def test_truncamento_vira_ia_indisponivel(snapshot_exemplo, com_chave):
    truncada = SimpleNamespace(model="claude-opus-5", stop_reason="max_tokens", content=[])

    with pytest.raises(ia.IAIndisponivel, match="truncada por limite de tokens"):
        ia.analisar(snapshot_exemplo, CONFIG, criar_cliente=lambda: ClienteFalso(truncada))


def test_erro_http_traz_o_status(snapshot_exemplo, com_chave):
    erro = RuntimeError("overloaded")
    erro.status_code = 529

    with pytest.raises(ia.IAIndisponivel, match=r"Erro da API Anthropic \(529\)"):
        ia.analisar(snapshot_exemplo, CONFIG, criar_cliente=lambda: ClienteFalso(falhar_com=erro))


def test_erro_de_conexao(snapshot_exemplo, com_chave):
    erro = ConnectionError("ECONNRESET")

    with pytest.raises(ia.IAIndisponivel, match="Falha de conexão"):
        ia.analisar(snapshot_exemplo, CONFIG, criar_cliente=lambda: ClienteFalso(falhar_com=erro))


def test_sdk_ausente_gera_mensagem_clara(snapshot_exemplo, com_chave):
    def sem_sdk():
        raise ImportError("No module named 'anthropic'")

    with pytest.raises(ia.IAIndisponivel, match="Pacote 'anthropic' nao instalado"):
        ia.analisar(snapshot_exemplo, CONFIG, criar_cliente=sem_sdk)


# ─────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────


def test_schema_exige_todos_os_campos_e_proibe_extras():
    assert ia.SCHEMA["required"] == [
        "resumo",
        "saude_carteira",
        "ativos",
        "carteira",
        "riscos",
        "fatos",
        "oportunidades",
        "contexto_mercado",
    ]
    assert ia.SCHEMA["additionalProperties"] is False


def test_indicadores_numericos_aceitam_null():
    pvp = ia.SCHEMA["properties"]["ativos"]["items"]["properties"]["p_vp"]
    assert pvp["anyOf"] == [{"type": "number"}, {"type": "null"}]

"""Contrato da chamada à API da Anthropic e montagem do prompt."""

import copy
import json
from types import SimpleNamespace

import pytest

from analise import ai_insights as ia
from analise import config_ia

CONFIG = {"max_fatos": 5, "max_oportunidades": 3}


class FluxoFalso:
    """Imita o contexto devolvido por `client.messages.stream(...)`."""

    def __init__(self, resposta):
        self.resposta = resposta

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def get_final_message(self):
        return self.resposta


class ClienteFalso:
    """Registra os parâmetros recebidos em cada canal (beta e normal)."""

    def __init__(self, resposta=None, falhar_com=None):
        self.resposta = resposta
        self.falhar_com = falhar_com
        self.chamadas = {"beta": [], "normal": []}
        self.beta = SimpleNamespace(
            messages=SimpleNamespace(stream=lambda **kw: self._responder(kw, "beta"))
        )
        self.messages = SimpleNamespace(stream=lambda **kw: self._responder(kw, "normal"))

    def _responder(self, parametros, canal):
        self.chamadas[canal].append(parametros)
        if self.falhar_com:
            raise self.falhar_com
        return FluxoFalso(self.resposta)


def dados_ia_validos(**overrides):
    """Resposta completa o bastante para passar por `_conferir_conteudo`.

    `snapshot_exemplo` tem um único ativo de renda variável (MXRF11) — é o que
    `ativos` precisa cobrir para a resposta não ser tratada como vazia.
    """
    base = {
        "resumo": "ok",
        "saude_carteira": "boa",
        "ativos": [{"ticker": "MXRF11", "comentario": "ok"}],
        "carteira": {"diversificacao": "ok"},
        "riscos": [],
        "fatos": [],
        "oportunidades": [],
        "contexto_mercado": "ok",
    }
    base.update(overrides)
    return base


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
def com_chave(env_ia):
    """Bloco completo do provedor anthropic no .env temporário."""
    env_ia(
        ANTHROPIC_ORIGEM_CHAVE="arquivo",
        ANTHROPIC_API_KEY="sk-ant-teste",
        ANTHROPIC_MODEL="claude-opus-5",
        ANTHROPIC_EFFORT="medium",
    )


# ─────────────────────────────────────────────
# Configuração
# ─────────────────────────────────────────────


def test_indisponivel_sem_chave(env_ia):
    env_ia(ANTHROPIC_MODEL="claude-opus-5", ANTHROPIC_EFFORT="medium")
    ok, motivo = ia.disponivel()

    assert ok is False
    assert "ANTHROPIC_API_KEY" in motivo


def test_indisponivel_sem_modelo(env_ia):
    env_ia(ANTHROPIC_API_KEY="sk-ant-teste")
    ok, motivo = ia.disponivel()

    assert ok is False
    assert "ANTHROPIC_MODEL" in motivo


def test_disponivel_com_chave(com_chave):
    assert ia.disponivel() == (True, "")


def test_modelo_e_effort_vem_do_arquivo(env_ia, monkeypatch):
    # O ambiente diz uma coisa, o arquivo outra: o arquivo é quem manda.
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-5")
    monkeypatch.setenv("ANTHROPIC_EFFORT", "low")
    env_ia(ANTHROPIC_MODEL="claude-sonnet-5", ANTHROPIC_EFFORT="high")

    assert ia.modelo() == "claude-sonnet-5"
    assert ia.effort() == "high"


def test_ambiente_atende_quando_o_arquivo_nao_define(env_ia, monkeypatch):
    env_ia(ANTHROPIC_API_KEY="sk-ant-teste")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-fable-5")
    monkeypatch.setenv("ANTHROPIC_EFFORT", "xhigh")

    assert ia.modelo() == "claude-fable-5"
    assert ia.effort() == "xhigh"


def test_effort_nenhum_vira_none(env_ia):
    env_ia(ANTHROPIC_MODEL="claude-sonnet-5", ANTHROPIC_EFFORT="nenhum")

    assert ia.effort() is None


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
    assert "[CDB] Inter — travado a 110% do CDI" in prompt
    assert "vence em 490 dias" in prompt
    assert "Renda mensal com risco moderado" in prompt
    assert "[atencao] Concentracao em MXRF11" in prompt
    assert "CDI: 14.9% a.a." in prompt
    assert "1 ativos de renda variável: MXRF11" in prompt
    assert "no máximo 5 fatos recentes" in prompt
    assert "no máximo 3 pontos de observação" in prompt


def test_prompt_anuncia_a_isencao_da_letra_de_credito(snapshot_exemplo):
    """Sem o aviso, o modelo leria 95% do CDI como pior que os 110% do CDB."""
    snapshot = copy.deepcopy(snapshot_exemplo)
    snapshot["posicoes"].append({
        **snapshot["posicoes"][1],
        "id": "d4",
        "tipo": "lci",
        "descricao": "LCI Sofisa 95% do CDI",
        "banco": "Sofisa",
        "emissor": "Sofisa",
        "taxa": 95.0,
        "rotulo_taxa": "95% do CDI",
        "isento_ir": True,
    })
    prompt = ia.montar_prompt(snapshot, CONFIG)

    assert "[LCI] Sofisa — travado a 95% do CDI, isento de IR" in prompt
    assert "[CDB] Inter — travado a 110% do CDI," in prompt


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


def test_recusa_sem_chave(snapshot_exemplo, env_ia):
    env_ia(ANTHROPIC_MODEL="claude-opus-5", ANTHROPIC_EFFORT="medium")

    with pytest.raises(ia.IAIndisponivel):
        ia.analisar(snapshot_exemplo, CONFIG)


def test_usa_o_canal_beta_com_fallback(snapshot_exemplo, com_chave):
    cliente = ClienteFalso(resposta_valida(dados_ia_validos()))

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
    assert parametros["tools"] == [{
        "type": "web_search_20260209",
        "name": "web_search",
        "cache_control": {"type": "ephemeral"},
    }]
    assert parametros["system"] == [{
        "type": "text",
        "text": ia.SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral"},
    }]
    assert parametros["max_tokens"] == config_ia.MAX_TOKENS_PADRAO
    assert parametros["messages"][0]["role"] == "user"

    assert dados["resumo"] == "ok"
    assert dados["_meta"]["provedor"] == "anthropic"
    assert dados["_meta"]["modelo"] == "claude-opus-5"
    assert dados["_meta"]["effort"] == "medium"
    assert dados["_meta"]["tokens_entrada"] == 1200
    assert dados["_meta"]["buscas_web"] == 6


def test_usa_o_canal_normal_sem_fallback(snapshot_exemplo, env_ia):
    env_ia(
        ANTHROPIC_API_KEY="sk-ant-teste",
        ANTHROPIC_MODEL="claude-sonnet-5",
        ANTHROPIC_EFFORT="medium",
    )
    cliente = ClienteFalso(resposta_valida(dados_ia_validos()))

    ia.analisar(snapshot_exemplo, CONFIG, criar_cliente=lambda: cliente)

    assert len(cliente.chamadas["normal"]) == 1
    assert cliente.chamadas["beta"] == []
    assert "fallbacks" not in cliente.chamadas["normal"][0]


def test_fallback_pode_ser_forcado_pelo_env(snapshot_exemplo, env_ia):
    env_ia(
        ANTHROPIC_API_KEY="sk-ant-teste",
        ANTHROPIC_MODEL="claude-sonnet-5",
        ANTHROPIC_EFFORT="medium",
        ANTHROPIC_FALLBACK="sim",
    )
    cliente = ClienteFalso(resposta_valida(dados_ia_validos()))

    ia.analisar(snapshot_exemplo, CONFIG, criar_cliente=lambda: cliente)

    assert len(cliente.chamadas["beta"]) == 1
    assert cliente.chamadas["beta"][0]["fallbacks"] == "default"


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


def test_resposta_com_resumo_vazio_vira_ia_indisponivel(snapshot_exemplo, com_chave):
    """Um provedor que não suporta os recursos pedidos (busca, effort) pode
    devolver um JSON válido e completo na forma, mas vazio no conteúdo — isso
    não pode ser tratado como sucesso, senão apaga a última leitura boa."""
    dados = dados_ia_validos(resumo="  ")
    cliente = ClienteFalso(resposta_valida(dados))

    with pytest.raises(ia.IAIndisponivel, match="resumo.*vazio"):
        ia.analisar(snapshot_exemplo, CONFIG, criar_cliente=lambda: cliente)


def test_resposta_sem_fichas_de_ativos_vira_ia_indisponivel(snapshot_exemplo, com_chave):
    dados = dados_ia_validos(ativos=[])
    cliente = ClienteFalso(resposta_valida(dados))

    with pytest.raises(ia.IAIndisponivel, match="MXRF11"):
        ia.analisar(snapshot_exemplo, CONFIG, criar_cliente=lambda: cliente)


def test_resposta_com_carteira_toda_vazia_vira_ia_indisponivel(snapshot_exemplo, com_chave):
    dados = dados_ia_validos(carteira={
        "diversificacao": "", "concentracao_setorial": "", "concentracao_gestor": "",
        "valuation": "", "renda": "", "conclusao": "",
    })
    cliente = ClienteFalso(resposta_valida(dados))

    with pytest.raises(ia.IAIndisponivel, match="carteira.*vazia"):
        ia.analisar(snapshot_exemplo, CONFIG, criar_cliente=lambda: cliente)


def test_erro_http_traz_o_status(snapshot_exemplo, com_chave):
    erro = RuntimeError("overloaded")
    erro.status_code = 529

    with pytest.raises(ia.IAIndisponivel, match=r"Erro da API de IA \(anthropic, HTTP 529\)"):
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
# Outro provedor pelo .env (Kimi)
# ─────────────────────────────────────────────


@pytest.fixture
def com_kimi(env_ia):
    env_ia(
        IA_PROVEDOR="kimi",
        KIMI_API_KEY="sk-kimi-teste",
        KIMI_MODEL="kimi-k2-thinking",
        KIMI_EFFORT="nenhum",
        KIMI_BASE_URL="https://api.moonshot.ai/anthropic",
        KIMI_BUSCA_WEB="nao",
        KIMI_MAX_TOKENS="8000",
    )


def test_kimi_usa_canal_normal_sem_effort_e_sem_busca(snapshot_exemplo, com_kimi):
    cliente = ClienteFalso(resposta_valida(dados_ia_validos()))

    dados = ia.analisar(snapshot_exemplo, CONFIG, criar_cliente=lambda: cliente)

    parametros = cliente.chamadas["normal"][0]
    assert cliente.chamadas["beta"] == []
    assert parametros["model"] == "kimi-k2-thinking"
    assert parametros["max_tokens"] == 8000
    assert "effort" not in parametros["output_config"]
    assert "tools" not in parametros
    assert dados["_meta"]["provedor"] == "kimi"
    assert dados["_meta"]["effort"] is None


def test_sem_busca_web_o_prompt_avisa_o_modelo(snapshot_exemplo, com_kimi):
    """Regressão: o endpoint compatível do Kimi não expõe busca web, e a regra
    'só afirme o que encontrou na busca' fazia o modelo devolver o relatório em
    branco. Sem a ferramenta, o aviso de compensação precisa ir no system."""
    cliente = ClienteFalso(resposta_valida(dados_ia_validos()))

    ia.analisar(snapshot_exemplo, CONFIG, criar_cliente=lambda: cliente)

    texto = cliente.chamadas["normal"][0]["system"][0]["text"]
    assert texto.startswith(ia.SYSTEM_PROMPT)
    assert "NÃO tem ferramenta de busca web" in texto


def test_base_url_do_env_chega_ao_cliente(com_kimi):
    cfg = config_ia.configuracao()

    cliente = ia._cliente_padrao(cfg)

    assert str(cliente.base_url).startswith("https://api.moonshot.ai/anthropic")


def test_cliente_sem_base_url_usa_o_padrao_do_sdk(com_chave):
    cfg = config_ia.configuracao()

    cliente = ia._cliente_padrao(cfg)

    assert "anthropic.com" in str(cliente.base_url)


def test_base_url_vazia_no_ambiente_nao_quebra_o_cliente(com_chave, monkeypatch):
    """Regressão: o painel de Configurações grava ANTHROPIC_BASE_URL="" quando o
    campo "URL base" fica em branco, e `scripts/analisar.py` recarrega esse
    .env com load_dotenv() — a variável some do arquivo (cfg["base_url"] vira
    None), mas continua presente e vazia no processo. O SDK lê essa variável
    por conta própria quando `base_url` não é passado, e uma string vazia
    (diferente de ausente) fazia o cliente tentar falar com um host vazio."""
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "")
    cfg = config_ia.configuracao()
    assert cfg["base_url"] is None, "pré-condição: nem arquivo nem ambiente têm valor utilizável"

    cliente = ia._cliente_padrao(cfg)

    assert "anthropic.com" in str(cliente.base_url)


# ─────────────────────────────────────────────
# Testar conexão (ping mínimo)
# ─────────────────────────────────────────────


def resposta_ping(texto="pong"):
    return SimpleNamespace(
        model="claude-opus-5",
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text=texto)],
        usage=SimpleNamespace(input_tokens=12, output_tokens=3),
    )


def test_testar_conexao_gasta_poucos_tokens_e_ignora_o_effort_configurado(com_chave):
    cliente = ClienteFalso(resposta_ping())

    resultado = ia.testar_conexao(criar_cliente=lambda: cliente)

    parametros = cliente.chamadas["beta"][0]
    assert parametros["max_tokens"] == 32
    assert parametros["output_config"]["effort"] == "low"
    assert "format" not in parametros["output_config"]
    assert "tools" not in parametros

    assert resultado["ok"] is True
    assert resultado["provedor"] == "anthropic"
    assert resultado["modelo"] == "claude-opus-5"
    assert resultado["resposta"] == "pong"
    assert resultado["truncado"] is False
    assert resultado["tokens_entrada"] == 12
    assert resultado["tokens_saida"] == 3


def test_testar_conexao_tolera_truncamento_por_tokens(com_chave):
    """Modelos com raciocínio interno (Kimi) podem cortar a resposta do ping
    sem que isso signifique falha de conexão — a chave e o modelo já
    responderam, só não coube no teto baixo do teste."""
    truncada = SimpleNamespace(
        model="claude-opus-5",
        stop_reason="max_tokens",
        content=[SimpleNamespace(type="text", text="po")],
        usage=SimpleNamespace(input_tokens=12, output_tokens=32),
    )

    resultado = ia.testar_conexao(criar_cliente=lambda: ClienteFalso(truncada))

    assert resultado["ok"] is True
    assert resultado["truncado"] is True
    assert resultado["resposta"] == "po"


def test_testar_conexao_ainda_recusa_quando_o_modelo_recusa(com_chave):
    """Truncamento é tolerado; recusa continua sendo um problema real."""
    recusa = SimpleNamespace(
        model="claude-opus-5",
        stop_reason="refusal",
        stop_details=SimpleNamespace(category="cyber"),
        content=[],
    )

    with pytest.raises(ia.IAIndisponivel, match="recusou responder"):
        ia.testar_conexao(criar_cliente=lambda: ClienteFalso(recusa))


def test_testar_conexao_de_um_provedor_especifico(env_ia):
    env_ia(
        IA_PROVEDOR="anthropic",
        ANTHROPIC_API_KEY="sk-ant-teste",
        ANTHROPIC_MODEL="claude-opus-5",
        ANTHROPIC_EFFORT="medium",
        KIMI_API_KEY="sk-kimi-teste",
        KIMI_MODEL="kimi-k2-thinking",
        KIMI_EFFORT="nenhum",
    )
    cliente = ClienteFalso(resposta_ping())

    resultado = ia.testar_conexao("kimi", criar_cliente=lambda: cliente)

    assert resultado["provedor"] == "kimi"
    parametros = cliente.chamadas["normal"][0]
    assert parametros["model"] == "kimi-k2-thinking"
    assert "output_config" not in parametros, "Kimi não usa effort"


def test_testar_conexao_sem_config_vira_ia_indisponivel():
    """`env_ia` já isola o .env real (autouse); sem nada gravado, falta ANTHROPIC_MODEL."""
    with pytest.raises(ia.IAIndisponivel, match="ANTHROPIC_MODEL"):
        ia.testar_conexao()


def test_testar_conexao_propaga_erro_http(com_chave):
    erro = RuntimeError("chave inválida")
    erro.status_code = 401

    with pytest.raises(ia.IAIndisponivel, match="HTTP 401"):
        ia.testar_conexao(criar_cliente=lambda: ClienteFalso(falhar_com=erro))


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


def test_prompt_declara_a_marcacao_a_mercado_do_tesouro(snapshot_exemplo):
    """Sem isso o modelo leria o ágio do papel como rendimento do período."""
    snapshot = copy.deepcopy(snapshot_exemplo)
    snapshot["posicoes"].append({
        "id": "c3",
        "tipo": "tesouro",
        "descricao": "Tesouro Prefixado 2031",
        "emissor": "Tesouro Nacional",
        "banco": None,
        "rotulo_taxa": "15.6% a.a.",
        "pagamento_juros": "vencimento",
        "valor_investido": 10000.0,
        "valor_atual": 13338.15,
        "valor_na_curva": 12732.97,
        "taxa_mercado_aa_pct": 14.34,
        "marcado_a_mercado": True,
        "dias_para_vencer": 1579,
        "vencido": False,
        "peso_pct": 31.0,
    })
    prompt = ia.montar_prompt(snapshot, CONFIG)

    assert "[Tesouro] Tesouro Prefixado 2031 — travado a 15.6% a.a." in prompt
    assert "marcado a mercado (na curva valeria R$ 12,732.97" in prompt
    assert "taxa de mercado hoje 14.34%" in prompt

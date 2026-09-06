"""Configuração do provedor de IA: precedência do .env e origem da chave."""

import pytest

from analise import config_ia

ANTHROPIC_MINIMO = {
    "ANTHROPIC_API_KEY": "sk-ant-teste",
    "ANTHROPIC_MODEL": "claude-opus-5",
    "ANTHROPIC_EFFORT": "medium",
}


# ─────────────────────────────────────────────
# Leitura do arquivo
# ─────────────────────────────────────────────


def test_arquivo_inexistente_devolve_dicionario_vazio(tmp_path):
    assert config_ia.ler_arquivo_env(tmp_path / "nao-existe.env") == {}


def test_ignora_comentarios_e_remove_aspas(tmp_path):
    arquivo = tmp_path / "a.env"
    arquivo.write_text(
        '# comentario\n# ANTHROPIC_MODEL=comentado\nexport A="um"\nB=\'dois\'\nC=tres\n',
        encoding="utf-8",
    )

    assert config_ia.ler_arquivo_env(arquivo) == {"A": "um", "B": "dois", "C": "tres"}


# ─────────────────────────────────────────────
# Precedência
# ─────────────────────────────────────────────


def test_arquivo_tem_precedencia_sobre_o_ambiente(env_ia, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MODEL", "do-ambiente")
    env_ia(**ANTHROPIC_MINIMO)

    assert config_ia.configuracao()["modelo"] == "claude-opus-5"


def test_ambiente_atende_o_que_o_arquivo_nao_define(env_ia, monkeypatch):
    env_ia(ANTHROPIC_API_KEY="sk-ant-teste", ANTHROPIC_MODEL="claude-opus-5")
    monkeypatch.setenv("ANTHROPIC_EFFORT", "max")

    assert config_ia.configuracao()["effort"] == "max"


def test_modelo_e_effort_nao_tem_padrao_no_codigo(env_ia):
    env_ia(ANTHROPIC_API_KEY="sk-ant-teste")

    with pytest.raises(config_ia.ConfiguracaoIAError, match="ANTHROPIC_MODEL"):
        config_ia.configuracao()


def test_effort_obrigatorio(env_ia):
    env_ia(ANTHROPIC_API_KEY="sk-ant-teste", ANTHROPIC_MODEL="claude-opus-5")

    with pytest.raises(config_ia.ConfiguracaoIAError, match="ANTHROPIC_EFFORT"):
        config_ia.configuracao()


# ─────────────────────────────────────────────
# Origem da chave
# ─────────────────────────────────────────────


def test_origem_arquivo_ignora_o_ambiente(env_ia, monkeypatch):
    """Com origem=arquivo, uma chave só no ambiente não serve."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-do-ambiente")
    env_ia(
        ANTHROPIC_ORIGEM_CHAVE="arquivo",
        ANTHROPIC_MODEL="claude-opus-5",
        ANTHROPIC_EFFORT="medium",
    )

    with pytest.raises(config_ia.ConfiguracaoIAError, match="somente do arquivo"):
        config_ia.configuracao()


def test_origem_ambiente_usa_a_variavel_nomeada(env_ia, monkeypatch):
    monkeypatch.setenv("CHAVE_CORPORATIVA", "sk-ant-do-ambiente")
    env_ia(
        ANTHROPIC_ORIGEM_CHAVE="ambiente",
        ANTHROPIC_VARIAVEL_CHAVE="CHAVE_CORPORATIVA",
        ANTHROPIC_API_KEY="sk-ant-do-arquivo",
        ANTHROPIC_MODEL="claude-opus-5",
        ANTHROPIC_EFFORT="medium",
    )

    assert config_ia.configuracao()["chave"] == "sk-ant-do-ambiente"


def test_origem_ambiente_exige_o_nome_da_variavel(env_ia):
    env_ia(ANTHROPIC_ORIGEM_CHAVE="ambiente", **ANTHROPIC_MINIMO)

    with pytest.raises(config_ia.ConfiguracaoIAError, match="ANTHROPIC_VARIAVEL_CHAVE"):
        config_ia.configuracao()


def test_origem_ambiente_falha_quando_a_variavel_nao_existe(env_ia, monkeypatch):
    monkeypatch.delenv("CHAVE_AUSENTE", raising=False)
    env_ia(
        ANTHROPIC_ORIGEM_CHAVE="ambiente",
        ANTHROPIC_VARIAVEL_CHAVE="CHAVE_AUSENTE",
        **ANTHROPIC_MINIMO,
    )

    with pytest.raises(config_ia.ConfiguracaoIAError, match="CHAVE_AUSENTE"):
        config_ia.configuracao()


def test_origem_invalida(env_ia):
    env_ia(ANTHROPIC_ORIGEM_CHAVE="cofre", **ANTHROPIC_MINIMO)

    with pytest.raises(config_ia.ConfiguracaoIAError, match="ORIGEM_CHAVE inválida"):
        config_ia.configuracao()


def test_exigir_chave_falso_descreve_sem_credencial(env_ia):
    env_ia(ANTHROPIC_MODEL="claude-opus-5", ANTHROPIC_EFFORT="medium")

    cfg = config_ia.configuracao(exigir_chave=False)

    assert (cfg["modelo"], cfg["effort"], cfg["chave"]) == ("claude-opus-5", "medium", "")


# ─────────────────────────────────────────────
# Outros provedores (Kimi)
# ─────────────────────────────────────────────


def test_prefixo_por_provedor():
    assert config_ia.prefixo("kimi") == "KIMI_"
    assert config_ia.prefixo("Moonshot AI") == "MOONSHOT_AI_"


def test_prefixo_invalido():
    with pytest.raises(config_ia.ConfiguracaoIAError, match="IA_PROVEDOR"):
        config_ia.prefixo("---")


def test_bloco_do_kimi(env_ia):
    env_ia(
        IA_PROVEDOR="kimi",
        KIMI_ORIGEM_CHAVE="arquivo",
        KIMI_API_KEY="sk-kimi-teste",
        KIMI_MODEL="kimi-k2-thinking",
        KIMI_EFFORT="nenhum",
        KIMI_BASE_URL="https://api.moonshot.ai/anthropic",
        KIMI_FALLBACK="nao",
        KIMI_BUSCA_WEB="nao",
        KIMI_MAX_TOKENS="8000",
    )

    cfg = config_ia.configuracao()

    assert cfg["provedor"] == "kimi"
    assert cfg["prefixo"] == "KIMI_"
    assert cfg["modelo"] == "kimi-k2-thinking"
    assert cfg["effort"] is None
    assert cfg["base_url"] == "https://api.moonshot.ai/anthropic"
    assert cfg["chave"] == "sk-kimi-teste"
    assert cfg["fallback"] is False
    assert cfg["busca_web"] is False
    assert cfg["max_tokens"] == 8000


def test_provedor_explicito_ignora_o_ia_provedor(env_ia):
    """Permite testar o bloco do Kimi mesmo com Anthropic ativo (IA_PROVEDOR)."""
    env_ia(
        IA_PROVEDOR="anthropic",
        **ANTHROPIC_MINIMO,
        KIMI_API_KEY="sk-kimi-teste",
        KIMI_MODEL="kimi-k2-thinking",
        KIMI_EFFORT="nenhum",
    )

    cfg = config_ia.configuracao(provedor="kimi")

    assert cfg["provedor"] == "kimi"
    assert cfg["modelo"] == "kimi-k2-thinking"


def test_provedor_ativo_nao_le_o_bloco_do_outro(env_ia):
    """Trocar IA_PROVEDOR troca o bloco inteiro, não só o modelo."""
    env_ia(IA_PROVEDOR="kimi", **ANTHROPIC_MINIMO)

    with pytest.raises(config_ia.ConfiguracaoIAError, match="KIMI_MODEL"):
        config_ia.configuracao()


# ─────────────────────────────────────────────
# Ajustes opcionais
# ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "modelo,esperado",
    [
        ("claude-opus-5", True),
        ("claude-fable-5", True),
        ("claude-sonnet-5", False),
        ("kimi-k2-thinking", False),
    ],
)
def test_fallback_auto_segue_a_familia_do_modelo(env_ia, modelo, esperado):
    env_ia(
        ANTHROPIC_API_KEY="sk-ant-teste",
        ANTHROPIC_MODEL=modelo,
        ANTHROPIC_EFFORT="medium",
        ANTHROPIC_FALLBACK="auto",
    )

    assert config_ia.configuracao()["fallback"] is esperado


def test_fallback_invalido(env_ia):
    env_ia(ANTHROPIC_FALLBACK="talvez", **ANTHROPIC_MINIMO)

    with pytest.raises(config_ia.ConfiguracaoIAError, match="ANTHROPIC_FALLBACK"):
        config_ia.configuracao()


def test_busca_web_invalida(env_ia):
    env_ia(ANTHROPIC_BUSCA_WEB="quem sabe", **ANTHROPIC_MINIMO)

    with pytest.raises(config_ia.ConfiguracaoIAError, match="ANTHROPIC_BUSCA_WEB"):
        config_ia.configuracao()


def test_max_tokens_invalido(env_ia):
    env_ia(ANTHROPIC_MAX_TOKENS="0", **ANTHROPIC_MINIMO)

    with pytest.raises(config_ia.ConfiguracaoIAError, match="ANTHROPIC_MAX_TOKENS"):
        config_ia.configuracao()

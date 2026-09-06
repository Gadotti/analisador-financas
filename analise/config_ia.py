"""Configuração do provedor de IA, lida do arquivo .env.

Nada de modelo nem de esforço é fixo no código: os valores vêm do `.env`, que
tem **precedência** sobre variáveis já presentes no ambiente — é o arquivo que
manda no que a análise usa. O ambiente só entra como retaguarda.

Cada provedor tem seu próprio bloco de variáveis, prefixado pelo nome em
maiúsculas: `IA_PROVEDOR=kimi` lê `KIMI_MODEL`, `KIMI_EFFORT`, `KIMI_BASE_URL`
e assim por diante. Trocar de provedor compatível com a API da Anthropic é,
portanto, uma edição no `.env` — não no código.

A chave da API tem origem declarada em `<PREFIXO>ORIGEM_CHAVE`:

- `arquivo`  — lida **somente** de `<PREFIXO>API_KEY` no `.env`; se faltar, falha;
- `ambiente` — lida da variável de ambiente cujo **nome** está em
  `<PREFIXO>VARIAVEL_CHAVE`; se essa variável não existir, falha.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from .paths import BASE_DIR

PROVEDOR_PADRAO = "anthropic"
ORIGEM_PADRAO = "arquivo"
ORIGENS = ("arquivo", "ambiente")
EFFORT_NENHUM = "nenhum"
MAX_TOKENS_PADRAO = 16000

# O parâmetro `fallbacks` (retomar automaticamente em outro modelo quando os
# classificadores de segurança recusam o pedido) só existe nestas famílias.
# Enviá-lo para os demais modelos resulta em erro 400. É a régua usada quando
# `<PREFIXO>FALLBACK=auto`; `sim` e `nao` decidem sem consultar a lista.
FAMILIAS_COM_FALLBACK = ("claude-opus-5", "claude-fable-5", "claude-mythos-5")

_LINHA = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
_VERDADEIROS = ("sim", "true", "1")
_FALSOS = ("nao", "não", "false", "0")


class ConfiguracaoIAError(RuntimeError):
    """Falta uma variável de configuração da IA ou ela tem valor inválido."""


def arquivo_env() -> Path:
    """Arquivo .env em uso. IA_ENV_FILE redireciona (é assim que os testes isolam)."""
    return Path(os.environ.get("IA_ENV_FILE") or (BASE_DIR / ".env"))


def _sem_aspas(bruto: str) -> str:
    texto = bruto.strip()
    if len(texto) >= 2 and texto[0] == texto[-1] and texto[0] in "\"'":
        return texto[1:-1]
    return texto


def ler_arquivo_env(arquivo: Path | str | None = None) -> dict[str, str]:
    """Pares chave=valor do .env. Dicionário vazio quando o arquivo não existe."""
    caminho = Path(arquivo) if arquivo else arquivo_env()
    try:
        conteudo = caminho.read_text(encoding="utf-8")
    except OSError:
        return {}

    valores: dict[str, str] = {}
    for linha in conteudo.splitlines():
        casa = _LINHA.match(linha)
        if casa:
            valores[casa.group(1)] = _sem_aspas(casa.group(2))
    return valores


def _valor(valores: dict[str, str], nome: str) -> str:
    """Valor da variável: o arquivo .env vence; o ambiente é a retaguarda."""
    do_arquivo = valores.get(nome, "").strip()
    return do_arquivo or os.environ.get(nome, "").strip()


def _exigir(valores: dict[str, str], nome: str, ajuda: str) -> str:
    lido = _valor(valores, nome)
    if not lido:
        raise ConfiguracaoIAError(f"{nome} não definida em {arquivo_env()}. {ajuda}")
    return lido


def prefixo(nome_provedor: str) -> str:
    """Prefixo das variáveis do provedor: 'kimi' -> 'KIMI_'."""
    limpo = re.sub(r"[^A-Za-z0-9]+", "_", nome_provedor).strip("_").upper()
    if not limpo:
        raise ConfiguracaoIAError(
            f"IA_PROVEDOR inválido: {nome_provedor!r}. "
            "Use um nome simples, como 'anthropic' ou 'kimi'."
        )
    return f"{limpo}_"


def suporta_fallback(nome_modelo: str) -> bool:
    """Indica se o modelo aceita o parâmetro `fallbacks` da API da Anthropic."""
    return nome_modelo.startswith(FAMILIAS_COM_FALLBACK)


def _chave_do_arquivo(valores: dict[str, str], pref: str) -> str:
    # Origem 'arquivo': a chave é lida somente do .env, nunca do ambiente.
    chave = valores.get(f"{pref}API_KEY", "").strip()
    if not chave:
        raise ConfiguracaoIAError(
            f"{pref}API_KEY não encontrada em {arquivo_env()}. Com "
            f"{pref}ORIGEM_CHAVE=arquivo a chave é lida somente do arquivo .env."
        )
    return chave


def _chave_do_ambiente(valores: dict[str, str], pref: str) -> str:
    nome_var = _exigir(
        valores,
        f"{pref}VARIAVEL_CHAVE",
        f"Com {pref}ORIGEM_CHAVE=ambiente, informe nela o nome da variável de "
        "ambiente que guarda a chave.",
    )
    chave = os.environ.get(nome_var, "").strip()
    if not chave:
        raise ConfiguracaoIAError(
            f"A variável de ambiente {nome_var} (indicada em {pref}VARIAVEL_CHAVE) "
            "está vazia ou não existe."
        )
    return chave


def origem_chave(valores: dict[str, str], pref: str) -> str:
    origem = (_valor(valores, f"{pref}ORIGEM_CHAVE") or ORIGEM_PADRAO).lower()
    if origem not in ORIGENS:
        raise ConfiguracaoIAError(
            f"{pref}ORIGEM_CHAVE inválida: {origem!r}. "
            f"Use um destes valores: {', '.join(ORIGENS)}."
        )
    return origem


def _chave_api(valores: dict[str, str], pref: str) -> str:
    if origem_chave(valores, pref) == "arquivo":
        return _chave_do_arquivo(valores, pref)
    return _chave_do_ambiente(valores, pref)


def _booleano(valores: dict[str, str], nome: str, padrao: bool) -> bool:
    bruto = _valor(valores, nome).lower()
    if not bruto:
        return padrao
    if bruto in _VERDADEIROS:
        return True
    if bruto in _FALSOS:
        return False
    raise ConfiguracaoIAError(
        f"{nome} inválida: {bruto!r}. Use 'sim' ou 'nao'."
    )


def _inteiro(valores: dict[str, str], nome: str, padrao: int) -> int:
    bruto = _valor(valores, nome)
    if not bruto:
        return padrao
    if not bruto.isdigit() or int(bruto) <= 0:
        raise ConfiguracaoIAError(
            f"{nome} inválida: {bruto!r}. Informe um número inteiro positivo."
        )
    return int(bruto)


def _fallback(valores: dict[str, str], pref: str, nome_modelo: str) -> bool:
    modo = (_valor(valores, f"{pref}FALLBACK") or "auto").lower()
    if modo in _VERDADEIROS:
        return True
    if modo in _FALSOS:
        return False
    if modo != "auto":
        raise ConfiguracaoIAError(
            f"{pref}FALLBACK inválida: {modo!r}. Use 'auto', 'sim' ou 'nao'."
        )
    return suporta_fallback(nome_modelo)


def configuracao(*, exigir_chave: bool = True, provedor: str | None = None) -> dict:
    """Configuração completa de um provedor.

    Levanta ConfiguracaoIAError quando falta algo. `exigir_chave=False` serve
    para exibir provedor, modelo e esforço sem precisar da credencial.
    `provedor` lê o bloco de um provedor específico (ex.: para testar a
    conexão com o Kimi mesmo com IA_PROVEDOR=anthropic); sem ele, vale o
    provedor ativo em IA_PROVEDOR.
    """
    valores = ler_arquivo_env()
    nome = provedor or _valor(valores, "IA_PROVEDOR") or PROVEDOR_PADRAO
    pref = prefixo(nome)

    modelo = _exigir(
        valores, f"{pref}MODEL", f"Defina nela o modelo do provedor '{nome}'."
    )
    esforco = _exigir(
        valores,
        f"{pref}EFFORT",
        f"Defina nela o esforço do provedor '{nome}' (low, medium, high, xhigh, "
        f"max) ou '{EFFORT_NENHUM}' para não enviar o campo.",
    )

    return {
        "provedor": nome.lower(),
        "prefixo": pref,
        "modelo": modelo,
        "effort": None if esforco.lower() == EFFORT_NENHUM else esforco,
        "base_url": _valor(valores, f"{pref}BASE_URL") or None,
        "origem_chave": origem_chave(valores, pref),
        "chave": _chave_api(valores, pref) if exigir_chave else "",
        "fallback": _fallback(valores, pref, modelo),
        "busca_web": _booleano(valores, f"{pref}BUSCA_WEB", True),
        "max_tokens": _inteiro(valores, f"{pref}MAX_TOKENS", MAX_TOKENS_PADRAO),
    }

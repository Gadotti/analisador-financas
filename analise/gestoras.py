"""Unificação determinística dos nomes de gestora vindos da IA.

O modelo descreve a mesma casa de formas levemente diferentes a cada execução —
"XP Asset Management (XP Vista)" e "XP Vista Asset Management (administração BTG
Pactual)" são a mesma gestora, e virariam duas linhas na alocação, escondendo a
concentração real. Aqui cada nome é reduzido a uma chave comparável e as
variantes são agrupadas sem consultar o modelo de novo.

A redução tem três passos: retirar o parêntese explicativo, descartar os termos
genéricos de razão social ("Asset Management", "Investimentos", "DTVM") e juntar
as chaves em que uma é prefixo da outra ("xp" e "xp vista").
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

# Palavras que aparecem na razão social de quase toda gestora e por isso não
# distinguem uma da outra. "Capital", "Partners" e "Hedge" ficam de fora de
# propósito: nesses nomes o termo é a marca, não o sufixo.
TERMOS_GENERICOS = frozenset({
    "asset", "assets", "management", "mgmt", "manager", "managers",
    "investimento", "investimentos", "investment", "investments", "invest",
    "gestao", "gestora", "gestor", "recursos", "wealth",
    "administracao", "administradora", "administrador", "adm",
    "dtvm", "ctvm", "distribuidora", "corretora",
    "titulos", "valores", "mobiliarios", "participacoes", "holding",
    "sa", "s", "a", "ltda", "ltd", "inc", "llc", "eireli",
})

CONECTIVOS = frozenset({"de", "da", "do", "das", "dos", "e", "the"})

_PARENTESES = re.compile(r"[(\[][^)\]]*[)\]]")
_ESPACOS = re.compile(r"\s{2,}")
_SEPARADORES = re.compile(r"[^0-9a-z]+")


def _sem_acentos(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def rotulo_limpo(nome: str) -> str:
    """Nome exibível: sem o parêntese explicativo e sem sobras de pontuação."""
    limpo = _ESPACOS.sub(" ", _PARENTESES.sub(" ", nome)).strip(" -–—,;:/")
    return limpo or nome.strip()


def chave_gestora(nome: str) -> tuple[str, ...]:
    """Tokens que identificam a gestora, já sem acento, caixa e razão social."""
    tokens = [t for t in _SEPARADORES.split(_sem_acentos(nome).lower()) if t]
    if not tokens:
        return (nome.strip().lower(),)
    distintivos = [t for t in tokens if t not in CONECTIVOS and t not in TERMOS_GENERICOS]
    return tuple(distintivos or tokens)


def _raiz_por_prefixo(chaves: set[tuple[str, ...]]) -> dict[tuple, tuple]:
    """Aponta cada chave para a mais curta que seja seu prefixo.

    ("xp",) e ("xp", "vista") caem no mesmo grupo; ("xp",) e ("xps",) não,
    porque a comparação é por token inteiro e não por letra.
    """
    raiz: dict[tuple, tuple] = {}
    anteriores: list[tuple[str, ...]] = []
    for chave in sorted(chaves, key=lambda c: (len(c), c)):
        prefixo = next((c for c in anteriores if chave[: len(c)] == c), None)
        raiz[chave] = raiz[prefixo] if prefixo else chave
        anteriores.append(chave)
    return raiz


def unificar_variantes(nomes: Iterable[str]) -> dict[str, str]:
    """Mapa do nome original para o nome canônico do seu grupo.

    O canônico é o rótulo mais curto do grupo — o que tende a ser o nome da
    casa sem as ressalvas que o modelo acrescenta. No empate, o que não estiver
    todo em caixa alta. Nomes vazios ficam de fora.
    """
    rotulos = {nome: rotulo_limpo(nome) for nome in nomes if nome and nome.strip()}
    chaves = {nome: chave_gestora(rotulo) for nome, rotulo in rotulos.items()}
    raiz = _raiz_por_prefixo(set(chaves.values()))

    grupos: dict[tuple, list[str]] = {}
    for nome, chave in chaves.items():
        grupos.setdefault(raiz[chave], []).append(nome)

    return {
        nome: min((rotulos[membro] for membro in membros), key=lambda r: (len(r), r.isupper(), r))
        for membros in grupos.values()
        for nome in membros
    }

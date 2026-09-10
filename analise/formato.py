"""Formatação dos números e do texto que saem para o terminal e o Telegram.

Espelha o papel de `web/js/formato.js` do outro lado do projeto: nada aqui
calcula, só apresenta. Tudo no padrão brasileiro — vírgula decimal, ponto de
milhar e data em dd/mm/aaaa — e sempre com um travessão para o valor ausente,
porque um campo vazio no relatório é indistinguível de um zero.
"""

from __future__ import annotations

import textwrap
from datetime import date, datetime

LARGURA = 78

# Rótulos e ícones compartilhados pelos dois formatos de saída — o relatório de
# terminal (`analise.report`) e as mensagens do Telegram (`analise.mensagem`).
SAUDE_ICONE = {"otima": "✅", "boa": "👍", "atencao": "⚠️", "alerta": "🚨"}
SAUDE_ROTULO = {"otima": "Ótima", "boa": "Boa", "atencao": "Atenção", "alerta": "Alerta"}
SEV_ICONE = {"info": "ℹ️", "atencao": "⚠️", "alerta": "🚨"}


def moeda(valor) -> str:
    if valor is None:
        return "—"
    txt = f"{abs(valor):,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
    return f"{'-' if valor < 0 else ''}R$ {txt}"


def data_br(iso: str) -> str:
    try:
        return date.fromisoformat(iso).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return iso or "-"


def num(valor, casas: int = 2) -> str:
    """Número no formato brasileiro, ou travessão quando indisponível."""
    if valor is None:
        return "—"
    return f"{valor:.{casas}f}".replace(".", ",")


def pct(valor, casas: int = 2, *, sinal: bool = True) -> str:
    """Percentual no formato brasileiro."""
    if valor is None:
        return "—"
    texto = f"{valor:{'+' if sinal else ''}.{casas}f}".replace(".", ",")
    return f"{texto}%"


def marcador(valor: float) -> str:
    """Bolinha de cor do resultado, para o terminal e o Telegram."""
    return "🟢" if valor > 0 else ("🔴" if valor < 0 else "⚪")


def quebrar(texto: str, recuo: str = "      ", largura: int = LARGURA) -> str:
    """Quebra um parágrafo respeitando a largura do relatório."""
    return textwrap.fill(
        texto or "", width=largura, initial_indent=recuo, subsequent_indent=recuo
    )


def secao(titulo: str) -> list[str]:
    return ["", "─" * LARGURA, f"  {titulo.upper()}", "─" * LARGURA, ""]


def leitura_herdada(data_snapshot: str, ia_meta: dict | None) -> str:
    """Data da análise que produziu as fichas, ou "" quando é a desta execução.

    Uma execução sem IA herda a leitura da anterior (ver `runner._reaproveitar_ia`);
    sem esta marca, relatório e mensagem apresentariam comentários antigos como
    se fossem de agora. Recebe o `_meta` solto porque a mensagem curta chega
    aqui pela seleção de `analise.relevancia`, que não carrega o snapshot.
    """
    gerado_em = (ia_meta or {}).get("gerado_em") or ""
    if not gerado_em or gerado_em[:10] == data_snapshot:
        return ""
    return datetime.fromisoformat(gerado_em).strftime("%d/%m/%Y às %H:%M")


def escapar_html(txt) -> str:
    """Escapa o que vai dentro do HTML restrito que o Telegram aceita."""
    return str(txt or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

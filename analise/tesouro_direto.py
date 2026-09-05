"""Taxas e preços dos títulos públicos, do Tesouro Transparente.

Fonte: o CSV "Taxas dos Títulos Ofertados pelo Tesouro Direto", publicado pelo
Tesouro Nacional no primeiro dia útil após o fechamento do mercado secundário.
Ele traz, por título e por pregão desde 2004, a taxa e o preço unitário (PU).

São 14 MB, e as duas leituras que fazemos custam coisas bem diferentes:

  - `cotacoes()` quer só o pregão mais recente. Como o arquivo vem ordenado do
    mais novo para o mais antigo, ele está nas primeiras linhas: a leitura para
    na primeira data diferente e fecha a conexão, sem baixar o resto. Uma
    requisição por execução atende todos os títulos da carteira.
  - `taxas_na_compra()` quer um pregão antigo, lá no fim do arquivo, então
    baixa tudo. Em compensação, taxa de pregão fechado não muda mais: o
    resultado vai para o cache sem prazo de validade e não se repete.

Os rótulos do arquivo são da ótica do INVESTIDOR, conforme os metadados
oficiais: "Taxa Compra" é a taxa com que ele compra o título (a que fica
travada na aplicação) e "Taxa Venda", a que recebe ao revender ao Tesouro
antes do vencimento — sempre um pouco pior. Trocá-las inverte o resultado.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime

import requests

from . import cache

TIMEOUT = 60
UA = {"User-Agent": "Mozilla/5.0 (compatible; PortfolioAnalyzer/1.0)"}

CSV_URL = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/"
    "df56aa42-484a-4a59-8184-7676580c81e3/resource/"
    "796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv"
)

TTL_COTACAO = 12 * 3600  # o arquivo muda uma vez por pregão

# `Tipo Titulo` do arquivo para cada par (indexador, pagamento dos juros) da
# carteira. É o casamento exato: o nome comercial do papel não precisa ser lido.
TIPO_TITULO = {
    ("SELIC", "vencimento"): "Tesouro Selic",
    ("PRE", "vencimento"): "Tesouro Prefixado",
    ("PRE", "semestral"): "Tesouro Prefixado com Juros Semestrais",
    ("IPCA", "vencimento"): "Tesouro IPCA+",
    ("IPCA", "semestral"): "Tesouro IPCA+ com Juros Semestrais",
}

COLUNAS = (
    "Tipo Titulo", "Data Vencimento", "Data Base",
    "Taxa Compra Manha", "Taxa Venda Manha",
    "PU Compra Manha", "PU Venda Manha", "PU Base Manha",
)


class TesouroIndisponivel(RuntimeError):
    """O arquivo do Tesouro Transparente não pôde ser lido."""


# ─────────────────────────────────────────────
# Leitura do arquivo
# ─────────────────────────────────────────────

def _decimal(texto: str) -> float:
    """Número no formato brasileiro do arquivo ("1.234,56") em float."""
    return float(texto.strip().replace(".", "").replace(",", "."))


def _data(texto: str) -> date:
    return datetime.strptime(texto.strip(), "%d/%m/%Y").date()


def _linha(bruta: str) -> dict | None:
    """Converte uma linha do CSV num dicionário, ou None se não for de dados."""
    campos = bruta.split(";")
    if len(campos) != len(COLUNAS) or campos[0].strip() == COLUNAS[0]:
        return None
    try:
        return {
            "tipo": campos[0].strip(),
            "vencimento": _data(campos[1]),
            "data_base": _data(campos[2]),
            "taxa_compra": _decimal(campos[3]),
            "taxa_venda": _decimal(campos[4]),
            "pu_compra": _decimal(campos[5]),
            "pu_venda": _decimal(campos[6]),
        }
    except ValueError:
        return None


@contextmanager
def _fluxo():
    """Abre o CSV para leitura linha a linha, fechando a conexão ao sair.

    Fechar cedo importa: é assim que `_linhas_do_ultimo_pregao` evita puxar os
    14 MB inteiros. Sair do `with` derruba o socket e o resto não desce.
    """
    try:
        resposta = requests.get(CSV_URL, headers=UA, timeout=TIMEOUT, stream=True)
        resposta.raise_for_status()
        resposta.encoding = "utf-8"
    except requests.RequestException as exc:
        raise TesouroIndisponivel(f"Tesouro Transparente indisponivel: {exc}") from None
    try:
        yield resposta.iter_lines(decode_unicode=True)
    finally:
        resposta.close()


def _linhas_do_ultimo_pregao() -> list[dict]:
    """Linhas do pregão mais recente, que abre o arquivo.

    O arquivo vem estritamente ordenado do pregão mais novo para o mais antigo,
    então o bloco do topo é o de hoje e a primeira data diferente encerra a
    leitura. O cabeçalho `Range` não serve aqui: este servidor responde 206 com
    o `Content-Range` certo e manda o corpo inteiro assim mesmo.
    """
    colhidas: list[dict] = []
    pregao = None
    with _fluxo() as linhas:
        for bruta in linhas:
            linha = _linha(bruta)
            if not linha:
                continue
            if pregao is None:
                pregao = linha["data_base"]
            if linha["data_base"] != pregao:
                break
            colhidas.append(linha)
    return colhidas


def _data_iso(valor: str) -> date:
    return date.fromisoformat(str(valor)[:10])


def _par_do_titulo(titulo: dict) -> tuple[str, str]:
    return titulo["indexador"], titulo.get("pagamento_juros") or "vencimento"


def _chave_titulo(indexador: str, pagamento_juros: str, vencimento: str) -> str:
    return f"{indexador}:{pagamento_juros}:{vencimento}"


# ─────────────────────────────────────────────
# Cotação do dia
# ─────────────────────────────────────────────

def _cotacoes_do_ultimo_pregao() -> dict:
    """Taxa e PU de revenda de todos os títulos do pregão mais recente."""
    linhas = _linhas_do_ultimo_pregao()
    if not linhas:
        raise TesouroIndisponivel("Tesouro Transparente devolveu um arquivo vazio.")

    pregao = max(linha["data_base"] for linha in linhas)
    par_por_rotulo = {rotulo: par for par, rotulo in TIPO_TITULO.items()}

    encontradas = {}
    for linha in linhas:
        par = par_por_rotulo.get(linha["tipo"])
        if not par or linha["data_base"] != pregao:
            continue
        chave = _chave_titulo(par[0], par[1], linha["vencimento"].isoformat())
        encontradas[chave] = {
            "taxa_venda_pct": linha["taxa_venda"],
            "pu_venda": linha["pu_venda"],
            "data_base": linha["data_base"].isoformat(),
        }
    return encontradas


def cotacoes(*, usar_cache: bool = True) -> dict:
    """Cotação de revenda do último pregão, indexada por título.

    Devolve sempre um dicionário; numa falha de rede vem só com a chave `erro`,
    para que a análise siga adiante sem marcação a mercado.
    """
    if usar_cache:
        em_cache = cache.obter("td_cotacoes", TTL_COTACAO)
        if em_cache is not None:
            return em_cache
    try:
        valor = _cotacoes_do_ultimo_pregao()
    except TesouroIndisponivel as exc:
        return {"erro": str(exc)}
    cache.definir("td_cotacoes", valor)
    return valor


def cotacao_de(cotacoes_do_dia: dict, titulo: dict) -> dict | None:
    """A cotação de um título dentro do mapa devolvido por `cotacoes()`."""
    indexador, pagamento = _par_do_titulo(titulo)
    chave = _chave_titulo(indexador, pagamento, titulo["data_vencimento"])
    return cotacoes_do_dia.get(chave)


# ─────────────────────────────────────────────
# Taxa travada na compra
# ─────────────────────────────────────────────

def _chave_compra(titulo: dict) -> str:
    indexador, pagamento = _par_do_titulo(titulo)
    alvo = _chave_titulo(indexador, pagamento, titulo["data_vencimento"])
    return f"td_compra:{alvo}:{titulo['data_aplicacao']}"


def _melhor_pregao(candidatos: dict, alvo: date) -> dict | None:
    """Pregão mais próximo até `alvo` — o dia da compra, ou o último antes dele.

    Uma aplicação em fim de semana, feriado ou dia sem negociação do papel cai
    no pregão anterior, que é o preço que valeu para aquela ordem.
    """
    if not candidatos:
        return None
    return candidatos[max(candidatos)]


def _procurar_compras(pendentes: dict) -> dict:
    """Varre o arquivo inteiro atrás do pregão de compra de cada título."""
    alvos = {}
    for pos_id, titulo in pendentes.items():
        alvos[pos_id] = (
            TIPO_TITULO[_par_do_titulo(titulo)],
            _data_iso(titulo["data_vencimento"]),
            _data_iso(titulo["data_aplicacao"]),
        )
    candidatos: dict[str, dict] = {pos_id: {} for pos_id in alvos}

    with _fluxo() as linhas:
        for bruta in linhas:
            linha = _linha(bruta)
            if not linha:
                continue
            for pos_id, (tipo, vencimento, aplicacao) in alvos.items():
                if (linha["tipo"] == tipo
                        and linha["vencimento"] == vencimento
                        and linha["data_base"] <= aplicacao):
                    candidatos[pos_id][linha["data_base"]] = linha

    achados = {}
    for pos_id, (_, _, aplicacao) in alvos.items():
        linha = _melhor_pregao(candidatos[pos_id], aplicacao)
        if linha:
            achados[pos_id] = {
                "taxa_pct": linha["taxa_compra"],
                "pu_compra": linha["pu_compra"],
                "data_base": linha["data_base"].isoformat(),
            }
    return achados


def taxas_na_compra(titulos: list[dict], *, usar_cache: bool = True) -> dict:
    """Taxa e PU travados na aplicação de cada título, indexados pelo id.

    Um pregão já fechado não muda mais, então cada resultado é gravado no cache
    sem prazo: o arquivo completo só é baixado quando entra um título novo na
    carteira. Título sem dado fica de fora do resultado.
    """
    achados: dict = {}
    pendentes: dict = {}

    for titulo in titulos:
        if _par_do_titulo(titulo) not in TIPO_TITULO:
            continue
        em_cache = (
            cache.obter(_chave_compra(titulo), cache.SEM_EXPIRAR) if usar_cache else None
        )
        if em_cache is not None:
            achados[titulo["id"]] = em_cache
        else:
            pendentes[titulo["id"]] = titulo

    if not pendentes:
        return achados

    try:
        encontrados = _procurar_compras(pendentes)
    except TesouroIndisponivel:
        return achados

    cache.definir_varios({
        _chave_compra(pendentes[pos_id]): dados for pos_id, dados in encontrados.items()
    })
    achados.update(encontrados)
    return achados

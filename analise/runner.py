"""Orquestra a análise completa e persiste o resultado.

Chamado pelo script isolado `scripts/analisar.py`, seja no terminal, pelo
agendador de tarefas ou disparado pela interface web — de modo que as três
origens produzam exatamente o mesmo resultado.
"""

from __future__ import annotations

import json
import time
from datetime import datetime

from . import ai_insights, analysis, config_ia, fundamentals, portfolio, relevancia
from .paths import execucoes_file, garantir_diretorios, history_dir, last_analysis_file

# Teto do log de execuções quando o cadastro não o declara. O valor real vem de
# `config["max_execucoes"]`, ajustável na tela de Configurações.
LIMITE_EXECUCOES_PADRAO = portfolio.CONFIG_PADRAO["max_execucoes"]


def executar(
    *,
    usar_ia: bool = True,
    usar_cache: bool = True,
    salvar: bool = True,
    analisar_com_ia=None,
) -> dict:
    """Roda a análise da carteira.

    A parte determinística sempre roda. A análise por IA é opcional e, se
    falhar, o resultado ainda é devolvido com o campo `ia_erro` preenchido.
    Sem leitura nova, as fichas da última análise salva são herdadas — ver
    `_reaproveitar_ia`.
    """
    inicio = time.monotonic()
    carteira = portfolio.load()
    # Uma leitura só da análise anterior, aproveitada por dois consumidores: a
    # herança das fichas de IA e a comparação dos indicadores macro.
    anterior = ultima_analise()
    snapshot = analysis.consolidar(carteira, usar_cache=usar_cache)

    resultado = {
        "snapshot": snapshot,
        "ia": None,
        "fundamentos": None,
        "ia_erro": None,
        "ia_solicitada": usar_ia,
        "ia_reaproveitada_de": None,
        "macro_anterior": _macro_anterior(anterior),
        "duracao_s": None,
    }

    if usar_ia:
        resultado["ia"], resultado["ia_erro"] = _analisar_com_ia(
            snapshot, carteira["config"], analisar_com_ia
        )
    if resultado["ia"] is None:
        _reaproveitar_ia(resultado, anterior)

    # Métricas derivadas das fichas: aritmética local, não estimativa do modelo.
    resultado["fundamentos"] = fundamentals.consolidar(snapshot, resultado["ia"])
    resultado["duracao_s"] = round(time.monotonic() - inicio, 1)

    if salvar:
        persistir(resultado, carteira["config"])

    return resultado


def _analisar_com_ia(snapshot: dict, config: dict, analisador) -> tuple[dict | None, str | None]:
    """Chama a IA e devolve `(leitura, erro)` — a falha nunca derruba o relatório."""
    if not snapshot["posicoes"]:
        return None, "Carteira vazia — nada a analisar."
    try:
        return (analisador or ai_insights.analisar)(snapshot, config), None
    except ai_insights.IAIndisponivel as exc:
        return None, str(exc)
    except Exception as exc:  # falha inesperada não derruba o relatório
        return None, f"Falha inesperada na analise por IA: {exc}"


def _macro_anterior(anterior: dict | None) -> dict | None:
    """Indicadores macro da análise anterior, para o bloco de mudança da mensagem.

    Só os três que a mensagem compara (`relevancia.macro_comparavel`), e não o
    `macro` inteiro: os índices e o horário de consulta não entram em
    comparação nenhuma, e este registro é gravado em disco a cada execução.

    Numa execução intradiária o "anterior" é a rodada anterior de hoje, e é
    exatamente essa a leitura desejada: a mudança de um indicador é anunciada
    uma vez, na rodada em que ela apareceu.
    """
    macro = ((anterior or {}).get("snapshot") or {}).get("macro")
    return relevancia.macro_comparavel(macro)


def _reaproveitar_ia(resultado: dict, anterior: dict | None) -> None:
    """Herda a leitura da última análise salva quando esta execução não tem uma.

    Uma execução sem IA (`--sem-ia`, o botão "Atualizar cotações") ou uma
    tentativa que falhou grava por cima do registro do dia. Sem esta herança o
    arquivo ficaria sem fichas e a alocação por classificação, segmento e
    gestora — além da tela de análise — sumiria da interface, mesmo havendo uma
    leitura válida em disco.

    As fichas são herdadas cruas: `fundamentals` recalcula pesos e valores com o
    snapshot de agora. `ia_reaproveitada_de` carrega a data de origem para que
    interface e relatório não apresentem a leitura antiga como recém-feita.

    `anterior` é a análise já lida por `executar`, e não uma segunda abertura
    do arquivo.
    """
    ia = (anterior or {}).get("ia")
    if not ia or not ia.get("ativos"):
        return
    resultado["ia"] = ia
    resultado["ia_reaproveitada_de"] = (ia.get("_meta") or {}).get("gerado_em")


def _identificacao_ia(registro: dict, status: str) -> dict:
    """Provedor, modelo e esforço a registrar para esta execução.

    Numa leitura nova o `_meta` descreve quem de fato respondeu — inclusive o
    modelo de retaguarda, quando houve fallback. Numa falha não existe `_meta`,
    e numa leitura herdada ele é o da análise antiga: aí o que interessa é a
    configuração que esta execução tentou usar.
    """
    vazio = {"provedor": None, "modelo": None, "effort": None, "buscas_web": None}
    if status == "sem_ia":
        return vazio
    if status == "sucesso":
        meta = (registro.get("ia") or {}).get("_meta") or {}
        return {campo: meta.get(campo) for campo in vazio}
    try:
        cfg = config_ia.configuracao(exigir_chave=False)
    except config_ia.ConfiguracaoIAError:
        return vazio
    return {**vazio, "provedor": cfg["provedor"], "modelo": cfg["modelo"], "effort": cfg["effort"]}


def _registro_execucao(registro: dict) -> dict:
    """Uma linha do log de execuções — o que a tela de Histórico lista."""
    totais = registro["snapshot"]["totais"]
    status = _status_execucao(registro)
    return {
        "gerado_em": registro["gerado_em"],
        "data": registro["snapshot"]["data"],
        "duracao_s": registro.get("duracao_s"),
        "status_ia": status,
        "ia_erro": registro.get("ia_erro"),
        "ia_reaproveitada_de": registro.get("ia_reaproveitada_de"),
        **_identificacao_ia(registro, status),
        "valor_atual": totais["valor_atual"],
        "resultado_pct": totais["resultado_pct"],
        "posicoes": totais["posicoes"],
    }


def _limite_execucoes(config: dict | None) -> int:
    """Quantas linhas o log guarda, conforme o cadastro.

    Um valor ausente ou ilegível cai no padrão; abaixo de 1 o log se apagaria
    inteiro, então esse é o piso.
    """
    try:
        limite = int((config or {}).get("max_execucoes", LIMITE_EXECUCOES_PADRAO))
    except (TypeError, ValueError):
        return LIMITE_EXECUCOES_PADRAO
    return max(1, limite)


def _anexar_execucao(registro: dict, limite: int) -> None:
    """Acrescenta esta execução ao log, descartando as mais antigas além do teto."""
    log = execucoes(limite=limite - 1) if limite > 1 else []
    log.append(_registro_execucao(registro))
    with open(execucoes_file(), "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def persistir(resultado: dict, config: dict | None = None) -> dict:
    registro = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        **resultado,
    }
    garantir_diretorios()
    with open(last_analysis_file(), "w", encoding="utf-8") as f:
        json.dump(registro, f, ensure_ascii=False, indent=2)

    arquivo = history_dir() / f"{resultado['snapshot']['data']}.json"
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(registro, f, ensure_ascii=False, indent=2)

    _anexar_execucao(registro, _limite_execucoes(config))
    return registro


def execucoes(limite: int = 60) -> list[dict]:
    """Log de execuções, da mais antiga para a mais recente."""
    try:
        with open(execucoes_file(), "r", encoding="utf-8") as f:
            registros = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []
    if not isinstance(registros, list):
        return []
    return registros[-limite:]


def ultima_analise() -> dict | None:
    try:
        with open(last_analysis_file(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _status_execucao(registro: dict) -> str:
    """Resume o resultado da IA numa execução, para a tela de Histórico.

    'sem_ia': não foi pedida (--sem-ia, botão "Atualizar cotações").
    'erro': foi pedida e falhou sem uma leitura anterior para herdar.
    'erro_recuperado': falhou, mas a leitura do dia anterior foi mantida —
    ver `_reaproveitar_ia`.
    'sucesso': leitura nova e válida nesta execução.
    """
    if not registro.get("ia_solicitada"):
        return "sem_ia"
    if registro.get("ia_erro"):
        return "erro_recuperado" if registro.get("ia_reaproveitada_de") else "erro"
    return "sucesso"


def historico(limite: int = 60) -> list[dict]:
    """Série histórica do valor da carteira, da data mais antiga para a mais recente."""
    arquivos = sorted(history_dir().glob("*.json"))[-limite:]
    serie = []
    for arquivo in arquivos:
        try:
            with open(arquivo, "r", encoding="utf-8") as f:
                dados = json.load(f)
            totais = dados["snapshot"]["totais"]
            serie.append({
                "data": dados["snapshot"]["data"],
                "valor_investido": totais["valor_investido"],
                "valor_atual": totais["valor_atual"],
                "resultado": totais["resultado"],
                "resultado_pct": totais["resultado_pct"],
                "saude": dados["snapshot"]["saude_carteira"],
            })
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    return serie

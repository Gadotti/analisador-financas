"""Análise qualitativa e fundamentalista da carteira via IA + busca web.

Camada OPCIONAL: exige o pacote `anthropic` instalado e o bloco do provedor
preenchido no `.env` (veja analise.config_ia). A análise determinística
(analise.analysis) funciona sem nada disso.

Provedor, modelo, esforço, endereço da API e origem da chave saem todos do
`.env` — nada disso é fixo aqui. Como Kimi e outros provedores expõem a mesma
API da Anthropic, basta apontar `<PREFIXO>BASE_URL` para eles.

A IA levanta os fundamentos de cada ativo (segmento, P/VP, DY, patrimônio,
gestora) e escreve a leitura qualitativa. Os números agregados da carteira
— médias ponderadas e concentrações — são calculados em analise.fundamentals
a partir dessas fichas, e não estimados pelo modelo.
"""

from __future__ import annotations

import json
from datetime import datetime

from . import config_ia, portfolio
from .config_ia import ConfiguracaoIAError, suporta_fallback  # noqa: F401

CACHE_EFEMERO = {"type": "ephemeral"}

# `cache_control` marca o fim de um trecho que não muda entre chamadas, para a
# API cobrar como leitura de cache (bem mais barata) a partir da segunda vez
# que aparece — dentro do próprio laço de busca web desta execução. Só vale
# para blocos de `system`, `tools` e `messages`; o schema de saída estruturada
# em `output_config` não é um desses blocos e não é coberto por isto.
FERRAMENTA_BUSCA = {
    "type": "web_search_20260209",
    "name": "web_search",
    "cache_control": CACHE_EFEMERO,
}
BETA_FALLBACK = "server-side-fallback-2026-07-01"


def modelo() -> str:
    """Modelo configurado no .env. Lido a cada chamada, sem valor padrão no código."""
    return config_ia.configuracao(exigir_chave=False)["modelo"]


def effort() -> str | None:
    """Esforço configurado no .env. None quando o provedor não deve recebê-lo."""
    return config_ia.configuracao(exigir_chave=False)["effort"]


SYSTEM_PROMPT = """Você é um analista de investimentos brasileiro, especialista em fundos
imobiliários (FIIs), ações da B3, renda fixa bancária (CDBs, LCIs e LCAs) e títulos
públicos federais (Tesouro Direto). Você produz relatórios de
carteira no padrão de uma casa de análise: fundamentos levantados ativo a ativo, seguidos
de uma leitura consolidada do conjunto.

Você recebe a fotografia de uma carteira real, já marcada a mercado. Use a busca web para
levantar, de cada ativo de renda variável:

- Classificação e segmento de atuação
- Gestora ou administradora (FIIs) / grupo controlador (ações)
- P/VP mais recente
- Dividend yield dos últimos 12 meses
- Patrimônio líquido do fundo ou valor de mercado da empresa
- Vacância física ou financeira, quando for fundo de tijolo
- Fatos recentes: proventos, resultados, aquisições, vendas de imóveis, eventos de
  crédito, comunicados ao mercado, mudanças de locatário

E também o cenário macro brasileiro atual: Selic, IPCA, IFIX, Ibovespa, curva de juros.

Regras de rigor:
- Só afirme o que encontrou na busca. Quando um indicador não estiver disponível, use
  null naquele campo em vez de estimar — um número inventado é pior que um campo vazio.
- Indique em `fonte` de onde veio a informação de cada ativo.
- Considere o peso de cada posição: um fato sobre 2% da carteira não pesa como um sobre 30%.
- Aponte correlações entre ativos que o investidor pode não ter percebido: sobreposição de
  segmento, concentração no mesmo gestor, exposição ao mesmo locatário ou devedor.
- Para a renda fixa bancária (CDB, LCI e LCA), considere vencimento, indexador e
  concentração por banco — o teto do FGC é de R$ 250 mil por CPF/instituição e é o mesmo
  para os três, somados.
- LCI e LCA são isentas de IR para a pessoa física: a taxa contratada nelas já é líquida,
  e por isso uma LCI a 95% do CDI pode render mais que um CDB a 105% no mesmo prazo. Ao
  comparar remunerações, compare-as líquidas. Elas também têm carência legal, então não
  as trate como reserva de liquidez.
- Títulos do Tesouro Direto já vêm marcados a mercado, pelo preço de revenda do último
  pregão: o valor informado é o que o investidor receberia vendendo hoje, e pode estar
  acima ou abaixo do valor na curva. Compare a taxa travada na compra com a taxa de
  mercado atual do mesmo papel — a diferença entre elas é o que explica o ágio ou o
  deságio, e um prefixado ou IPCA+ longo oscila muito mais que um Tesouro Selic.
- O Tesouro não é coberto pelo FGC — quem responde pelo papel é o Tesouro Nacional, o
  menor risco de crédito do país, então não trate a concentração nele como concentração
  de emissor bancário.
- Nenhuma posição de renda fixa (CDB, LCI, LCA, Tesouro Direto) entra na lista `ativos` —
  comente-as nos campos de análise da carteira.
- Ordene os riscos do mais relevante para o menos relevante.
- Escreva em português do Brasil, objetivo e sem jargão desnecessário.
- Você não é assessor de investimentos: descreva cenários e pontos de atenção, sem
  recomendar compra ou venda de forma imperativa."""


# Nem todo provedor expõe busca web (o endpoint compatível com Anthropic da
# Moonshot, por exemplo, só aceita ferramentas `custom`). Sem este aviso o
# modelo continua lendo "só afirme o que encontrou na busca" e devolve o
# relatório em branco — foi exatamente o que aconteceu na primeira execução
# com o Kimi.
INSTRUCAO_SEM_BUSCA = """

ATENÇÃO — nesta execução você NÃO tem ferramenta de busca web. Onde as instruções acima
mandam pesquisar, responda pelo conhecimento que você já tem: preencha os campos de texto
normalmente e reserve o null para os indicadores numéricos de que não tem segurança. Em
`fonte`, diga que a informação vem do seu conhecimento prévio, com o período a que se
refere, e não de consulta ao vivo."""


def system_prompt(com_busca: bool) -> str:
    """Instruções do sistema, ajustadas à existência da ferramenta de busca."""
    return SYSTEM_PROMPT if com_busca else SYSTEM_PROMPT + INSTRUCAO_SEM_BUSCA


def _numero_ou_nulo(descricao: str) -> dict:
    return {"anyOf": [{"type": "number"}, {"type": "null"}], "description": descricao}


SCHEMA = {
    "type": "object",
    "properties": {
        "resumo": {
            "type": "string",
            "description": "Sumário executivo da carteira em 3 a 5 frases.",
        },
        "saude_carteira": {
            "type": "string",
            "enum": ["otima", "boa", "atencao", "alerta"],
        },
        "ativos": {
            "type": "array",
            "description": (
                "Ficha técnica de cada ativo de renda variável. "
                "Não inclua renda fixa: CDB, LCI, LCA nem Tesouro Direto."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "nome": {"type": "string", "description": "Nome do fundo ou da empresa."},
                    "classificacao": {
                        "type": "string",
                        "enum": ["tijolo", "papel", "hibrido", "fof", "acao", "outro"],
                    },
                    "segmento": {
                        "type": "string",
                        "description": "Ex.: Logística, Agências bancárias, Lajes corporativas, Bancos.",
                    },
                    "gestora": {
                        "type": "string",
                        "description": "Gestora do FII ou grupo controlador da empresa.",
                    },
                    "p_vp": _numero_ou_nulo("Preço sobre valor patrimonial, ex.: 0.93."),
                    "dy_12m_pct": _numero_ou_nulo("Dividend yield de 12 meses em %, ex.: 12.4."),
                    "patrimonio": {
                        "type": "string",
                        "description": "PL do fundo ou valor de mercado, formatado. Ex.: 'R$ 7,57 bi'.",
                    },
                    "vacancia_pct": _numero_ou_nulo("Vacância em %, apenas para fundos de tijolo."),
                    "comentario": {
                        "type": "string",
                        "description": "Dois a quatro períodos sobre a tese, o portfólio e o momento do ativo.",
                    },
                    "risco": {
                        "type": "string",
                        "description": "Principal risco específico deste ativo.",
                    },
                    "fonte": {"type": "string"},
                },
                "required": [
                    "ticker", "nome", "classificacao", "segmento", "gestora",
                    "p_vp", "dy_12m_pct", "patrimonio", "vacancia_pct",
                    "comentario", "risco", "fonte",
                ],
                "additionalProperties": False,
            },
        },
        "carteira": {
            "type": "object",
            "description": "Leitura do conjunto, não dos ativos isolados.",
            "properties": {
                "diversificacao": {
                    "type": "string",
                    "description": "Como a carteira se distribui entre tipos de ativo e o que isso significa.",
                },
                "concentracao_setorial": {
                    "type": "string",
                    "description": "Sobreposições de segmento e correlação entre os ativos.",
                },
                "concentracao_gestor": {
                    "type": "string",
                    "description": "Repetição de gestora, administrador, banco emissor ou locatário.",
                },
                "valuation": {
                    "type": "string",
                    "description": "Leitura dos múltiplos frente ao momento de mercado.",
                },
                "renda": {
                    "type": "string",
                    "description": "Leitura da geração de renda: yield, previsibilidade e sensibilidade a juros.",
                },
                "conclusao": {
                    "type": "string",
                    "description": "Fechamento em 2 a 4 frases: o que a carteira é hoje e o que mais merece atenção.",
                },
            },
            "required": [
                "diversificacao", "concentracao_setorial", "concentracao_gestor",
                "valuation", "renda", "conclusao",
            ],
            "additionalProperties": False,
        },
        "riscos": {
            "type": "array",
            "description": "Riscos da carteira, do mais relevante para o menos relevante.",
            "items": {
                "type": "object",
                "properties": {
                    "titulo": {"type": "string"},
                    "descricao": {"type": "string"},
                    "severidade": {"type": "string", "enum": ["info", "atencao", "alerta"]},
                    "ativos": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["titulo", "descricao", "severidade", "ativos"],
                "additionalProperties": False,
            },
        },
        "fatos": {
            "type": "array",
            "description": "Fatos recentes e datados sobre os ativos da carteira.",
            "items": {
                "type": "object",
                "properties": {
                    "ativo": {"type": "string"},
                    "titulo": {"type": "string"},
                    "descricao": {"type": "string"},
                    "severidade": {"type": "string", "enum": ["info", "atencao", "alerta"]},
                    "fonte": {"type": "string"},
                },
                "required": ["ativo", "titulo", "descricao", "severidade", "fonte"],
                "additionalProperties": False,
            },
        },
        "oportunidades": {
            "type": "array",
            "description": "Pontos de observação coerentes com o perfil e a alocação atual.",
            "items": {
                "type": "object",
                "properties": {
                    "tipo": {
                        "type": "string",
                        "enum": ["compra", "monitorar", "setor", "macro", "renda_fixa", "rebalanceamento"],
                    },
                    "titulo": {"type": "string"},
                    "descricao": {"type": "string"},
                    "ativos": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["tipo", "titulo", "descricao", "ativos"],
                "additionalProperties": False,
            },
        },
        "contexto_mercado": {
            "type": "string",
            "description": "Cenário macro atual e seu efeito concreto sobre esta carteira.",
        },
    },
    "required": [
        "resumo", "saude_carteira", "ativos", "carteira",
        "riscos", "fatos", "oportunidades", "contexto_mercado",
    ],
    "additionalProperties": False,
}


class IAIndisponivel(RuntimeError):
    """A análise por IA não pôde ser executada."""


def disponivel() -> tuple[bool, str]:
    """Indica se a análise por IA pode ser executada e o motivo em caso negativo."""
    try:
        config_ia.configuracao()
    except ConfiguracaoIAError as exc:
        return False, str(exc)
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False, "Pacote 'anthropic' nao instalado (pip install anthropic)."
    return True, ""


# ─────────────────────────────────────────────
# Montagem do prompt
# ─────────────────────────────────────────────

# Como cada tipo de renda fixa é anunciado ao modelo.
ROTULO_RENDA_FIXA = {"cdb": "CDB", "lci": "LCI", "lca": "LCA", "tesouro": "Tesouro"}

def _linha_renda_fixa(p: dict) -> str:
    """Uma posição de renda fixa descrita para o modelo.

    O papel bancário é identificado pelo banco (é o que importa para o FGC); o
    título público, pelo nome do papel, que já carrega família e vencimento. A
    isenção de IR vai escrita porque é ela que torna a taxa comparável: sem o
    aviso, o modelo lê "95% do CDI" como uma remuneração pior do que é.
    """
    venc = "VENCIDO" if p["vencido"] else f"vence em {p['dias_para_vencer']} dias"
    bancario = p["tipo"] in portfolio.TIPOS_BANCARIOS
    rotulo = ROTULO_RENDA_FIXA[p["tipo"]]
    identificacao = p["banco"] if bancario else p["descricao"]
    tributacao = ", isento de IR" if p.get("isento_ir") else ""
    cupom = f", juros {p['pagamento_juros']}" if p["pagamento_juros"] != "vencimento" else ""
    mercado = (
        f", marcado a mercado (na curva valeria R$ {p['valor_na_curva']:,.2f}"
        f", taxa de mercado hoje {p['taxa_mercado_aa_pct']:g}%)"
        if p.get("marcado_a_mercado") else ""
    )
    return (
        f"- [{rotulo}] {identificacao} — travado a {p['rotulo_taxa']}{tributacao}{cupom}, "
        f"aplicado R$ {p['valor_investido']:,.2f}, "
        f"valor atual R$ {p['valor_atual']:,.2f}{mercado}, {venc}, "
        f"peso {p['peso_pct']:.1f}% da carteira"
    )


def _resumo_posicoes(snapshot: dict) -> str:
    linhas = []
    for p in snapshot["posicoes"]:
        if p["tipo"] in portfolio.TIPOS_VARIAVEL:
            rotulo = "FII" if p["tipo"] == "fii" else "Ação"
            linhas.append(
                f"- [{rotulo}] {p['ticker']}: {p['quantidade']:g} cotas, "
                f"PM R$ {p['preco_medio']:.2f}, cotação R$ {p['preco_atual'] or 0:.2f}, "
                f"resultado {p['resultado_pct']:+.1f}%, peso {p['peso_pct']:.1f}% da carteira"
            )
        else:
            linhas.append(_linha_renda_fixa(p))
    return "\n".join(linhas)


def _resumo_alertas(snapshot: dict) -> str:
    alertas = snapshot["alertas"]
    if not alertas:
        return "Nenhum alerta automático foi gerado pelos cálculos."
    return "\n".join(f"- [{a['severidade']}] {a['titulo']}: {a['descricao']}" for a in alertas)


def montar_prompt(snapshot: dict, config: dict) -> str:
    hoje = datetime.now().strftime("%d/%m/%Y")
    t = snapshot["totais"]
    macro = snapshot["macro"]

    classes = " | ".join(
        f"{c['rotulo']} {c['peso_pct']:.1f}%" for c in snapshot["classes"].values()
    )
    tickers = [p["ticker"] for p in snapshot["posicoes"] if p["tipo"] in portfolio.TIPOS_VARIAVEL]

    return (
        f"Data de hoje: {hoje}\n\n"
        f"## Carteira (valores já calculados, não recalcule)\n"
        f"Total investido: R$ {t['valor_investido']:,.2f}\n"
        f"Valor atual: R$ {t['valor_atual']:,.2f} ({t['resultado_pct']:+.2f}%)\n"
        f"Alocação: {classes}\n\n"
        f"### Posições\n{_resumo_posicoes(snapshot)}\n\n"
        f"### Perfil declarado pelo investidor\n"
        f"{snapshot.get('perfil') or 'Não informado.'}\n\n"
        f"### Alertas automáticos já detectados pelo sistema\n{_resumo_alertas(snapshot)}\n\n"
        f"### Indicadores de referência já coletados\n"
        f"CDI: {macro['cdi_anual_pct']['valor']}% a.a. | "
        f"Selic meta: {macro['selic_meta_pct']['valor']}% a.a. | "
        f"IPCA 12m: {macro['ipca_12m_pct'].get('valor')}%\n\n"
        f"## Sua tarefa\n"
        f"1. Levante a ficha técnica de cada um destes {len(tickers)} ativos de renda "
        f"variável: {', '.join(tickers) or 'nenhum'}. Um item em `ativos` por ticker, "
        f"na mesma ordem.\n"
        f"2. Escreva a análise consolidada da carteira em `carteira`, tratando "
        f"diversificação, concentração setorial, concentração de gestor ou emissor, "
        f"valuation, geração de renda e a conclusão.\n"
        f"3. Liste os riscos em ordem de relevância.\n"
        f"4. Traga no máximo {int(config['max_fatos'])} fatos recentes e no máximo "
        f"{int(config['max_oportunidades'])} pontos de observação.\n"
        f"5. Feche com a leitura do contexto macro conectada a esta carteira.\n\n"
        f"Não repita os alertas automáticos acima — o investidor já os viu; use-os apenas "
        f"como contexto."
    )


# ─────────────────────────────────────────────
# Chamada à API
# ─────────────────────────────────────────────

def extrair_json(blocos) -> dict:
    """Pega o último bloco de texto da resposta e converte em dict."""
    textos = [b.text for b in blocos if b.type == "text" and b.text.strip()]
    if not textos:
        raise IAIndisponivel("A resposta da IA não trouxe nenhum bloco de texto.")
    bruto = textos[-1].strip()
    if bruto.startswith("```"):
        bruto = bruto.split("```")[1]
        bruto = bruto[4:] if bruto.startswith("json") else bruto
        bruto = bruto.strip()
    try:
        return json.loads(bruto)
    except json.JSONDecodeError as exc:
        raise IAIndisponivel(f"A IA não retornou JSON válido: {exc}") from None


def _cliente_padrao(cfg: dict):
    """Cria o cliente oficial. Import tardio: o SDK só carrega quando é usado.

    `base_url` vem do .env — é o que permite apontar para um provedor
    compatível com a API da Anthropic (Kimi, por exemplo) sem tocar no código.
    """
    import os

    import anthropic

    argumentos = {"api_key": cfg["chave"]}
    if cfg["base_url"]:
        argumentos["base_url"] = cfg["base_url"]
    else:
        # cfg["base_url"] só fica vazio quando nem o arquivo nem o ambiente têm
        # um valor utilizável (config_ia._valor já tentou os dois) — mas o SDK
        # lê ANTHROPIC_BASE_URL do processo por conta própria quando o
        # argumento não é passado, e uma variável presente-porém-vazia (comum
        # quando o painel de Configurações grava "ANTHROPIC_BASE_URL=" em
        # branco e o script recarrega o .env com load_dotenv) faz o cliente
        # tentar falar com um host vazio em vez de cair no padrão do SDK.
        os.environ.pop("ANTHROPIC_BASE_URL", None)
    return anthropic.Anthropic(**argumentos)


def montar_parametros(snapshot: dict, config: dict, cfg: dict) -> dict:
    """Corpo da requisição, montado a partir da configuração do provedor."""
    output_config: dict = {"format": {"type": "json_schema", "schema": SCHEMA}}
    if cfg["effort"]:
        output_config["effort"] = cfg["effort"]

    parametros = {
        "model": cfg["modelo"],
        "max_tokens": cfg["max_tokens"],
        "system": [
            {
                "type": "text",
                "text": system_prompt(cfg["busca_web"]),
                "cache_control": CACHE_EFEMERO,
            }
        ],
        "output_config": output_config,
        "messages": [{"role": "user", "content": montar_prompt(snapshot, config)}],
    }
    if cfg["busca_web"]:
        parametros["tools"] = [FERRAMENTA_BUSCA]
    return parametros


def _criar_resposta(client, parametros: dict, cfg: dict):
    """Dispara a chamada em streaming e traduz qualquer falha em IAIndisponivel.

    Streaming não é detalhe de desempenho aqui: o SDK recusa de saída uma
    requisição comum cujo `max_tokens` permita passar de 10 minutos de geração,
    e é justamente o caso de um modelo de raciocínio com teto alto — sem isto,
    subir <PREFIXO>MAX_TOKENS troca o truncamento por um erro de conexão.
    `get_final_message()` devolve a mesma mensagem completa do canal comum.
    """
    try:
        if cfg["fallback"]:
            # Se os classificadores recusarem, a própria API refaz o pedido
            # no modelo de retaguarda recomendado, na mesma chamada.
            fluxo = client.beta.messages.stream(
                **parametros, betas=[BETA_FALLBACK], fallbacks="default"
            )
        else:
            fluxo = client.messages.stream(**parametros)
        with fluxo as transmissao:
            return transmissao.get_final_message()
    except Exception as exc:
        status = getattr(exc, "status_code", None)
        if status is not None:
            mensagem = getattr(exc, "message", None) or str(exc)
            raise IAIndisponivel(
                f"Erro da API de IA ({cfg['provedor']}, HTTP {status}): {mensagem}"
            ) from None
        raise IAIndisponivel(
            f"Falha de conexão com a API de IA ({cfg['provedor']}): {exc}"
        ) from None


def _conferir_conteudo(dados: dict, snapshot: dict) -> None:
    """Detecta uma resposta 'vazia': JSON válido e schema respeitado, mas sem
    substância real. O `output_config.format` garante a forma da resposta, não
    que o modelo pesquisou e escreveu algo — um provedor que não suporta a
    ferramenta de busca ou o `effort` pedido pode devolver um rascunho mínimo
    (campos obrigatórios preenchidos com string vazia ou lista vazia) em vez
    de recusar. Sem esta checagem essa leitura vazia some silenciosamente por
    cima da última leitura válida em `persistir`."""
    if not (dados.get("resumo") or "").strip():
        raise IAIndisponivel("A IA devolveu o resumo da carteira ('resumo') vazio.")

    tickers = [
        p["ticker"] for p in snapshot["posicoes"] if p["tipo"] in portfolio.TIPOS_VARIAVEL
    ]
    if tickers and not dados.get("ativos"):
        raise IAIndisponivel(
            f"A IA não preencheu a ficha de nenhum dos {len(tickers)} ativos de "
            f"renda variável esperados ({', '.join(tickers)}). Confira se o "
            "provedor configurado suporta a busca web e o esforço ('effort') "
            "pedidos no .env."
        )

    carteira = dados.get("carteira") or {}
    if not any((valor or "").strip() for valor in carteira.values()):
        raise IAIndisponivel("A IA devolveu a leitura da carteira ('carteira') vazia.")


def _conferir_parada(resposta, cfg: dict, *, exigir_completo: bool = True) -> None:
    """`exigir_completo=False` tolera truncamento (usado no ping de teste: a
    recusa ainda é um problema de configuração, mas um corte por tokens já
    prova que a chave e o modelo respondem — só não coube na resposta)."""
    if resposta.stop_reason == "refusal":
        categoria = getattr(getattr(resposta, "stop_details", None), "category", None)
        sufixo = f" ({categoria})" if categoria else ""
        raise IAIndisponivel(f"A IA recusou responder a esta solicitação{sufixo}.")
    if exigir_completo and resposta.stop_reason == "max_tokens":
        raise IAIndisponivel(
            "A resposta da IA foi truncada por limite de tokens. Reduza o número "
            f"de posições ou aumente {cfg['prefixo']}MAX_TOKENS no arquivo .env."
        )


def testar_conexao(provedor: str | None = None, *, criar_cliente=None) -> dict:
    """Ping mínimo à API do provedor informado (ou o ativo em IA_PROVEDOR).

    Não usa `montar_parametros`: sem schema, sem ferramenta de busca e sem o
    esforço configurado no `.env` (que é para a análise real) — só confirma
    que a chave e o modelo respondem, gastando o mínimo de tokens.
    """
    try:
        cfg = config_ia.configuracao(provedor=provedor)
    except ConfiguracaoIAError as exc:
        raise IAIndisponivel(str(exc)) from None

    try:
        client = (criar_cliente or (lambda: _cliente_padrao(cfg)))()
    except ImportError as exc:
        raise IAIndisponivel(
            f"Pacote 'anthropic' nao instalado (pip install -r requirements.txt): {exc}"
        ) from None

    parametros = {
        "model": cfg["modelo"],
        # Modelos com raciocínio interno (ex.: Kimi) gastam tokens pensando
        # antes de responder mesmo num "pong" — 32 dá essa margem sem deixar
        # de ser um teste barato.
        "max_tokens": 32,
        "messages": [{"role": "user", "content": "Responda só: pong"}],
    }
    if cfg["effort"]:
        parametros["output_config"] = {"effort": "low"}

    resposta = _criar_resposta(client, parametros, cfg)
    _conferir_parada(resposta, cfg, exigir_completo=False)

    texto = next((b.text for b in resposta.content if b.type == "text"), "")
    return {
        "ok": True,
        "provedor": cfg["provedor"],
        "modelo": resposta.model,
        "resposta": texto.strip(),
        # Um corte por tokens aqui não é falha: a chave e o modelo já
        # responderam, só não coube no teto baixo deste ping.
        "truncado": resposta.stop_reason == "max_tokens",
        "tokens_entrada": getattr(resposta.usage, "input_tokens", None),
        "tokens_saida": getattr(resposta.usage, "output_tokens", None),
    }


def analisar(snapshot: dict, config: dict, *, criar_cliente=None) -> dict:
    """Executa a análise qualitativa. Levanta IAIndisponivel em caso de falha.

    `criar_cliente` permite injetar um cliente alternativo nos testes.
    """
    ok, motivo = disponivel()
    if not ok:
        raise IAIndisponivel(motivo)

    cfg = config_ia.configuracao()

    try:
        client = (criar_cliente or (lambda: _cliente_padrao(cfg)))()
    except ImportError as exc:
        raise IAIndisponivel(
            f"Pacote 'anthropic' nao instalado (pip install -r requirements.txt): {exc}"
        ) from None

    parametros = montar_parametros(snapshot, config, cfg)
    resposta = _criar_resposta(client, parametros, cfg)
    _conferir_parada(resposta, cfg)

    dados = extrair_json(resposta.content)
    _conferir_conteudo(dados, snapshot)
    dados["_meta"] = {
        "provedor": cfg["provedor"],
        "modelo": resposta.model,
        "effort": cfg["effort"],
        "tokens_entrada": getattr(resposta.usage, "input_tokens", None),
        "tokens_saida": getattr(resposta.usage, "output_tokens", None),
        "buscas_web": getattr(
            getattr(resposta.usage, "server_tool_use", None), "web_search_requests", None
        ),
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
    }
    return dados

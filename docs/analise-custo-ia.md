# Análise de custo da IA — alternativas para reduzir o gasto por execução

> Gerado em 2026-09-17 a partir de uma análise de mercado solicitada pelo usuário. Revisado
> em 2026-09-22 para incorporar a busca web nova da Moonshot/Kimi. Nenhum código do projeto
> foi alterado para produzir este documento.

## Contexto

Configuração atual (`.env`): provedor `anthropic`, modelo `claude-sonnet-5`, esforço
`medium`, com busca web ativa. Custo relatado pelo usuário: ~US$ 0,44 por execução da
análise com IA. Tentativa anterior com a API do Moonshot (Kimi) foi descartada por não
oferecer busca web.

## O que os dados reais do sistema mostram

Do último registro de sucesso em `data/last_analysis.json` (carteira de 27 posições, 6 de
renda variável):

| Item | Valor real |
|---|---|
| Modelo | `claude-sonnet-5` |
| Esforço | `medium` |
| Tokens de entrada (turno final) | 3.019 → US$ 0,006 |
| Tokens de saída | 9.498 → US$ 0,095 |
| Buscas web | 12 → US$ 0,12 (a US$ 0,01/busca) |
| **Subtotal identificável** | **≈ US$ 0,22** |

O restante até chegar nos ~US$ 0,44 relatados é, com grande probabilidade, o conteúdo das
páginas lidas nas 12 buscas — cobrado como tokens de entrada durante o laço de busca
interno, que o campo `tokens_entrada` capturado em `analise/ai_insights.py` não reflete por
inteiro — mais a escrita do cache do prompt de sistema. Ou seja: **busca web e o conteúdo
que ela traz de volta correspondem a pelo menos metade do custo**, não o modelo em si.

## Por que "outro provedor compatível com a Anthropic" não resolve

A ferramenta `web_search_20260209` é executada **nos servidores da própria Anthropic**,
não pelo modelo do provedor de destino. É por isso que o Kimi/Moonshot não faz busca mesmo
apontando `KIMI_BASE_URL` para um endpoint compatível com a API da Anthropic: o provedor
devolve o modelo, mas não o serviço de busca por trás da ferramenta. Qualquer outro
"compatível com Anthropic" esbarraria na mesma limitação (inclusive um eventual acesso ao
Grok via esse formato, que a própria documentação da xAI descreve como em depreciação).
Essa rota está, na prática, esgotada — trocar de fornecedor *de verdade* significa sair da
API da Anthropic, o que é mudança de código, não de `.env`.

## Novidade (22/09/2026) — a Moonshot passou a oferecer busca web nativa

A tentativa anterior com o Kimi foi descartada porque, apontando `KIMI_BASE_URL` para o
endpoint compatível com a Anthropic, não havia serviço de busca por trás da ferramenta — a
Moonshot só expunha o modelo, não a busca. Isso mudou: a Moonshot lançou três ferramentas
próprias, fora do caminho compatível com a Anthropic:

| Ferramenta | Endpoint | Preço | O que faz |
|---|---|---|---|
| Web Search | `POST /v1/tools/search` | US$ 0,002/chamada | busca (1–20 resultados), com `include_content` opcional para trazer a página inteira |
| Web Search Pro | `POST /v1/tools/search_pro` | US$ 0,003/chamada | busca com filtro por até 5 domínios, janela temporal e `chunks` (trechos com score de relevância) |
| Fetch | `POST /v1/tools/fetch` | US$ 0,002/chamada | extrai uma URL específica e devolve o conteúdo em Markdown |

Cobrança só incide em chamada bem-sucedida com resultado não vazio — busca sem resultado ou
erro HTTP não é cobrada. As três não cobram tokens adicionais pelo conteúdo devolvido (isso
é diferente da ferramenta legada `$web_search`, que será descontinuada em outubro/2026 e
embutia o conteúdo nos tokens de conclusão).

**A diferença que importa para este projeto não é o preço — é a arquitetura.** A ferramenta
`web_search_20260209` da Anthropic é executada **inteiramente no servidor da Anthropic**:
basta declarar o `tool` na chamada e uma única resposta já vem com as buscas feitas. As três
ferramentas da Moonshot são **endpoints REST separados do `chat/completions`**: a
documentação não menciona formato compatível com tool-calling da OpenAI ou da Anthropic, e o
fluxo descrito é o cliente (não o modelo, sozinho) orquestrar o laço — chamar o modelo,
decidir chamar `search` ou `search_pro`, injetar o resultado de volta como contexto e só
então continuar a conversa (e, se for o caso, chamar `fetch` para uma URL específica). Isso é
o mesmo nível de trabalho que reescrever para o Perplexity, mencionado na Análise B: um
caminho novo em `analise/ai_insights.py`, com laço de chamadas própio, não uma linha nova no
`.env`.

Ainda assim, o preço por chamada é uma fração do da Anthropic: US$ 0,002–0,003 contra
US$ 0,01 por busca — e a análise de hoje faz 12 buscas, então só nessa linha a troca cortaria
algo como US$ 0,10 por execução (de ~US$ 0,12 para ~US$ 0,03), antes mesmo de considerar o
modelo. Somando o preço do próprio modelo Kimi, que também caiu desde a tentativa anterior:

| Modelo | Entrada (cache hit / miss) | Saída | Unidade |
|---|---|---|---|
| `kimi-k2.6` | US$ 0,16 / US$ 0,95 | US$ 4,00 | 1M tokens |
| `kimi-k2.7-code` | US$ 0,19 / US$ 0,95 | US$ 4,00 | 1M tokens |
| `kimi-k3` | US$ 3,00 (cache hit US$ 0,30) | US$ 15,00 | 1M tokens |

`kimi-k2.6`/`kimi-k2.7-code` continuam mais baratos que o Sonnet 5 atual (US$ 2 / US$ 10) em
entrada e saída; `kimi-k3` já custa mais que o Sonnet 5 em saída. Nenhum dos três resolve a
questão de qualidade de síntese que já pesava contra o Kimi na tentativa anterior — a busca
nova remove o obstáculo que inviabilizava o teste, não a incerteza sobre a qualidade do
relatório.

### Não existe SDK oficial da Moonshot

A documentação da própria Moonshot não oferece um pacote próprio. Para chat/completions ela
recomenda usar o **SDK da OpenAI ou o da Anthropic**, apontando `base_url` para os servidores
dela — é exatamente o que `KIMI_BASE_URL` já faz hoje em `_cliente_padrao`
(`analise/ai_insights.py:412-434`). Para as três ferramentas de busca (`search`, `search_pro`,
`fetch`), porém, os exemplos da documentação são requisição HTTP crua: `requests.post()` em
Python, `fetch()` nativo em Node, `curl` em bash — nenhuma biblioteca própria por trás.

Na prática isso não muda o esforço de desenvolvimento: `requests` já é dependência do projeto
(`market.cotacao`, `tesouro_direto.py`), então não há pacote novo para instalar em nenhum dos
dois caminhos (usar o cliente `anthropic` já existente para o chat + `requests` para a busca,
ou trocar tudo por um cliente HTTP próprio). Um SDK dedicado só teria embrulhado a chamada da
busca; o laço de orquestração — pedir busca, chamá-la, devolver o resultado ao modelo — teria
que ser escrito de qualquer forma.

### O que precisaria mudar no código para usar a busca do Kimi

Usando o SDK da Anthropic (como hoje, com `KIMI_BASE_URL`) ou trocando por outro cliente HTTP,
o trabalho é o mesmo em essência, porque o obstáculo não é o SDK — é que a busca da Moonshot
não é uma ferramenta server-side, então o laço de tool-use precisa ser escrito à mão em
`analise/ai_insights.py`:

1. **Ferramenta anunciada ao modelo por provedor, não fixa.** `FERRAMENTA_BUSCA`
   (`ai_insights.py:32-36`) hoje é uma constante única, do tipo `web_search_20260209` —
   server-side, só a Anthropic sabe executá-la. Para o Kimi ela precisaria virar uma
   ferramenta `custom` (nome, descrição, `input_schema` com o texto da busca), montada
   condicionalmente a partir de `cfg["provedor"]` em `montar_parametros`. O flag
   `<PREFIXO>BUSCA_WEB` já existe (`config_ia.configuracao()["busca_web"]`), mas hoje só liga
   ou desliga a mesma ferramenta — passaria a precisar dizer também **qual variante** usar.
2. **Laço de tool-use.** `_criar_resposta` (`ai_insights.py:461-490`) faz uma chamada só, em
   streaming, e devolve a mensagem final — porque a busca da Anthropic se resolve sozinha
   dentro dessa chamada. Com o Kimi, quando `resposta.stop_reason == "tool_use"`, o código
   precisa: extrair o(s) bloco(s) `tool_use` do conteúdo, chamar `requests.post` no endpoint
   certo da Moonshot (`/v1/tools/search`, `/search_pro` ou `/fetch`, a depender do que o
   modelo pediu), devolver o resultado como um bloco `tool_result` numa nova mensagem, e
   repetir a chamada ao modelo — até ele parar de pedir busca ou até um teto de iterações
   (sem teto, uma resposta mal formada do modelo entraria num laço sem fim).
3. **Segunda chamada de rede, sem cobertura pelos testes atuais.** A suíte de `pytest` isola
   rede com a fixture `rede`, que troca `requests.get`; a chamada à Moonshot seria `POST`
   para um domínio novo, então essa fixture precisaria de uma rota nova. Mais importante: os
   pontos de injeção de dependência de `analise/ai_insights.py` (`criar_cliente`, documentado
   no `CLAUDE.md`) cobrem só o cliente do modelo — a chamada de busca é uma chamada HTTP
   separada, então precisaria de um segundo ponto de injeção (algo como
   `analisar(..., criar_cliente=..., buscar=...)`) para os testes conseguirem rodar sem rede.
4. **Metadados da execução.** `dados["_meta"]["buscas_web"]` (`ai_insights.py:612-614`) lê
   `resposta.usage.server_tool_use.web_search_requests` — um campo que só existe porque a
   busca é executada pela Anthropic e contada por ela. Com o Kimi, essa contagem teria que
   ser feita pelo próprio código, somando as chamadas do laço acima.
5. **Onde a resposta "vazia" é detectada não muda.** `_conferir_conteudo`
   (`ai_insights.py:493-517`) e `INSTRUCAO_SEM_BUSCA` (`ai_insights.py:105-111`) continuam
   valendo — inclusive `INSTRUCAO_SEM_BUSCA` teria que deixar de ser "sem busca = sem
   ferramenta nenhuma" e passar a cobrir também "a ferramenta existe, mas é a variante Kimi".

Nenhum desses pontos é grande isoladamente, mas juntos formam uma reescrita real do caminho de
chamada — o mesmo porte do trabalho já estimado para o Perplexity na Análise B, não um ajuste
de configuração.

## Análise A — ajustes dentro da própria Anthropic (sem trocar de fornecedor)

| Alavanca | Como aplicar | Economia esperada (referência publicada pela Anthropic para trabalho de pesquisa/conhecimento) | Risco |
|---|---|---|---|
| Baixar `ANTHROPIC_EFFORT` de `medium` para `low` | edição no `.env` | `low` costuma ceder 1 a 3 pontos de qualidade por **1/3 a metade** do custo nesse tipo de tarefa; `medium` já captura 70–85% da qualidade do padrão pelo custo atual | Baixo–médio: já se está em `medium`, então o próximo degrau natural é `low` |
| Testar `claude-haiku-4-5` | trocar `ANTHROPIC_MODEL` e usar `ANTHROPIC_EFFORT=nenhum` (Haiku não aceita `effort`) | metade do preço por token (US$ 1 / US$ 5 vs US$ 2 / US$ 10) | Alto para este caso: Haiku rende bem em tarefas objetivas e de alto volume, mas a análise pede síntese (concentração, correlação entre ativos, riscos ponderados) — exatamente o tipo de tarefa em que modelos menores perdem mais qualidade |
| Cache de prompt | já está ativo (`cache_control` no system prompt, `analise/ai_insights.py`) | ganho marginal adicional — a maior parte do prompt (posições do dia) muda a cada execução e não é cacheável | — |
| Limitar `max_uses` da ferramenta de busca | reduziria as 12 buscas (maior fatia identificável do custo) | proporcional ao corte no número de buscas | Exige alteração de código — fora do escopo desta análise |

**Recomendação prática:** testar `ANTHROPIC_EFFORT=low` primeiro (é só editar o `.env`, sem
tocar em código) e comparar o relatório gerado com o de hoje usando `--previa-telegram` e a
tela de Análise. Cada teste roda o modelo de verdade e tem custo — vale rodar 2–3 dias em
paralelo antes de decidir.

## Análise B — outros fornecedores do mercado (exigiria trocar o cliente da API)

| Fornecedor / modelo | Preço por 1M tokens (entrada/saída) | Custo da busca web | Compatível com a arquitetura atual? |
|---|---|---|---|
| Claude Sonnet 5 (atual) | US$ 2 / US$ 10 | US$ 10/1000 buscas + tokens do conteúdo | — |
| Claude Haiku 4.5 | US$ 1 / US$ 5 | idem | Sim, só `.env` |
| Kimi (`kimi-k2.6`, Moonshot) | US$ 0,16–0,95 / US$ 4 | Search US$ 0,002/chamada, Search Pro US$ 0,003, Fetch US$ 0,002 (sem token extra pelo conteúdo) | Não — busca fora do formato compatível com Anthropic, exige laço de tool-calling próprio (ver seção acima) |
| Google Gemini 3.7 Flash | US$ 0,75 / US$ 3,75 | Grounding: US$ 14/1000 consultas (5.000 grátis/mês) | Não — SDK `google-genai` próprio |
| Google Gemini 3.1 Pro | US$ 2 / US$ 12 | idem | Não |
| OpenAI (modelo intermediário atual) | varia por tier | Web search: US$ 10/1000 chamadas + tokens do conteúdo | Não — Responses API própria |
| Perplexity Sonar Pro | US$ 3 / US$ 15 | busca embutida no preço da requisição (US$ 6–14/1000 requisições, não por busca individual) | Não, mas via `requests` puro (já é dependência do projeto) — formato de resposta parecido com OpenAI |
| xAI Grok 4.6 | US$ 2 / US$ 6 (cache US$ 0,50) | Web/X Search: US$ 5/1000 chamadas | Incerto — compatibilidade com SDK Anthropic está sendo descontinuada segundo a documentação da xAI |

O destaque é o **Perplexity Sonar Pro**: desenhado para "buscar fatos atuais e responder
com citações" — o caso de uso deste projeto — e cobra a busca **por requisição**, não por
busca individual. Como a análise dispara várias buscas por ticker (12 buscas para 6
ativos), um modelo que empacota isso numa taxa fixa por requisição tende a sair mais barato
que pagar US$ 0,01 por busca × N. A contrapartida é que ele não fala a API da Anthropic:
adotá-lo significa escrever um caminho alternativo em `analise/ai_insights.py` (novo
formato de requisição/resposta, sem `output_config`/`effort`/`cache_control` como hoje) —
desenvolvimento real, não configuração.

## Resumo

1. **Sem tocar em código:** baixar o esforço para `low` no `.env` e comparar a qualidade —
   é a alavanca com maior chance de corte de custo (até ~50%) sem trocar de modelo nem
   perder a busca web.
2. **Sem tocar em código, porém mais arriscado:** testar Haiku 4.5 — mais barato, mas risco
   real de piorar a síntese qualitativa.
3. **Com desenvolvimento futuro:** Perplexity Sonar Pro continua o candidato mais alinhado
   ao formato de custo atual (busca por ticker, preço por requisição). A busca nova da
   Moonshot/Kimi entra como um segundo candidato de mesmo porte de esforço — não mais
   descartável por falta de busca, mas ainda exigindo escrever um laço de tool-calling
   próprio em `analise/ai_insights.py`, já que não fala o formato compatível com a
   Anthropic. Preço por busca mais baixo (US$ 0,002–0,003 vs US$ 0,01), mas a incerteza
   sobre qualidade de síntese que pesava contra o Kimi antes continua sem resposta.
4. **Nenhuma opção testada de verdade ainda.** Todas as recomendações acima partem de preço
   de tabela, não de uma execução real da carteira — antes de trocar de modelo ou de
   fornecedor em produção, vale rodar `--previa-telegram` (ou a tela de Análise) em paralelo
   por alguns dias e comparar o relatório gerado, não só o custo.

## Fontes

- [Gemini API Pricing | Google AI for Developers](https://ai.google.dev/gemini-api/docs/pricing)
- [Grounding with Google Search | Gemini API](https://ai.google.dev/gemini-api/docs/google-search)
- [OpenAI API Pricing: Full Breakdown of Costs (Sep 2026)](https://developer.puter.com/tutorials/openai-api-pricing/)
- [Perplexity API Pricing In 2026](https://www.cloudzero.com/blog/perplexity-api-pricing/)
- [Sonar Pro API Pricing 2026](https://pricepertoken.com/pricing-page/model/perplexity-sonar-pro)
- [Grok API Pricing (Sep 2026)](https://mem0.ai/blog/xai-grok-api-pricing)
- [xAI Grok API – Chat Completions Endpoint](https://medium.com/@bmskmike/xai-grok-api-chat-completions-endpoint-full-technical-reference-integration-guide-80c7fed45210)
- [Moonshot/Kimi — Web Search Pricing](https://platform.kimi.ai/docs/pricing/websearch)
- [Moonshot/Kimi — Web Search API](https://platform.kimi.ai/docs/api/tools-search)
- [Moonshot/Kimi — Web Search Pro API](https://platform.kimi.ai/docs/api/tools-search-pro)
- [Moonshot/Kimi — Fetch API](https://platform.kimi.ai/docs/api/tools-fetch)
- [Moonshot/Kimi — Model Pricing](https://platform.kimi.ai/docs/pricing)

# Análise de custo da IA — alternativas para reduzir o gasto por execução

> Gerado em 2026-09-17 a partir de uma análise de mercado solicitada pelo usuário. Nenhum
> código do projeto foi alterado para produzir este documento.

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
3. **Com desenvolvimento futuro:** Perplexity Sonar Pro é o candidato mais alinhado ao
   formato de custo atual (busca por ticker), mas exige reescrever o cliente da chamada à
   IA.

## Fontes

- [Gemini API Pricing | Google AI for Developers](https://ai.google.dev/gemini-api/docs/pricing)
- [Grounding with Google Search | Gemini API](https://ai.google.dev/gemini-api/docs/google-search)
- [OpenAI API Pricing: Full Breakdown of Costs (Sep 2026)](https://developer.puter.com/tutorials/openai-api-pricing/)
- [Perplexity API Pricing In 2026](https://www.cloudzero.com/blog/perplexity-api-pricing/)
- [Sonar Pro API Pricing 2026](https://pricepertoken.com/pricing-page/model/perplexity-sonar-pro)
- [Grok API Pricing (Sep 2026)](https://mem0.ai/blog/xai-grok-api-pricing)
- [xAI Grok API – Chat Completions Endpoint](https://medium.com/@bmskmike/xai-grok-api-chat-completions-endpoint-full-technical-reference-integration-guide-80c7fed45210)

# CLAUDE.md

Orientações para o Claude Code trabalhar neste repositório.

## O que é

Sistema local de análise de carteira de investimentos brasileira (FIIs, ações da B3 e CDBs).
Roda inteiramente na máquina do usuário: dados em arquivos JSON, servidor web ouvindo apenas
em `127.0.0.1`.

**O projeto é bilíngue, e a divisão é deliberada:**

| Metade | Linguagem | Responsabilidade |
|---|---|---|
| `analise/` + `scripts/analisar.py` | Python 3.10+ | Todo o cálculo, a IA e o Telegram |
| `src/` + `web/` | Node.js 20.11+, ESM | Cadastro da carteira, servidor e interface |

Não porte lógica de uma metade para a outra. A regra de negócio da análise mora **só** no
Python; o cadastro e a apresentação moram **só** no Node.

## Comandos

```bash
# Análise (Python)
python scripts/analisar.py --sem-ia    # cálculo no terminal, sem chamar a API
python scripts/analisar.py --help      # todas as flags
python -m pytest                       # testes do motor de análise
python -m pytest tests_analise/test_fixed_income.py -q

# Aplicação (Node)
npm start                              # servidor em http://127.0.0.1:8765
npm start -- --porta 9000 --sem-navegador
npm test                               # Jest
npm run coverage
npm test -- test/server.test.js        # um arquivo só
```

## Code Standards

### Style

- Functions: 4–20 lines. Files: under 500 lines. Split by responsibility.
- Names: specific and unique. Avoid `data`, `handler`, `Manager`. Prefer names that return <5 grep hits.
- Early returns over nested ifs.
- Exception messages must include the offending value and expected shape.
- No code duplication. Extract shared logic into a function/module.
- Se baseie em boas práticas do Clean Code e do SOLID

### Test-after-change workflow

After every code change, run `npm test` and inspect the output. If any test fails:
1. Read the failure message and identify the root cause.
2. Fix the code. If the code it's not the problem, fix the test itself if necessary (never disable or delete the failing test).
3. Run `npm test` again.
4. Repeat until all tests pass before considering the task done.

## Arquitetura

### A regra central: a análise é um script Python isolado

`scripts/analisar.py` é o **único ponto do sistema que chama a API de IA e o
Telegram**. Roda de três formas, sempre com o mesmo resultado:

1. Direto no terminal;
2. Pelo Agendador de Tarefas do Windows (`agendar_tarefa.ps1`);
3. Como processo filho do servidor Node, via `src/server/analiseExterna.js`, que faz
   `spawn(python, [script, "--json", ...])` e lê o JSON do stdout.

Para isso funcionar, `--json` escreve **apenas o JSON no stdout**; todo o progresso vai para
o stderr. Se você adicionar saída ao script, respeite essa separação — é o contrato com o
servidor. Erros são devolvidos como `{"erro": "..."}` no stdout com código de saída 1.

**O Node nunca importa o pacote `analise/`** e não tem SDK da Anthropic instalado. Para
saber se os botões devem ficar habilitados ele usa `src/server/ambiente.js`, que apenas
confere a configuração declarada no `.env` (via `src/config/configIa.js`) e as variáveis
do Telegram.

### Quem escreve cada arquivo de dados

Uma regra por arquivo, para não haver duas validações divergentes:

| Arquivo | Escreve | Lê |
|---|---|---|
| `data/portfolio.json` | Node (`src/core/portfolio.js`) | Node e Python |
| `data/last_analysis.json` | Python (`analise/runner.py`) | Node e Python |
| `data/history/*.json` | Python | Node e Python |
| `data/cache.json` | Python (`analise/market.py`) | Python |

Por isso `analise/portfolio.py` é **somente leitura** — sem CRUD, sem gravação, sem
migração de formato. Se precisar de uma nova regra de validação de posição, ela vai em
`src/core/portfolio.js`.

### Injeção de dependência

Dois pontos de extensão existem para permitir testes sem rede:

- `analise/runner.py` → `executar(analisar_com_ia=...)` substitui o analisador de IA.
- `analise/ai_insights.py` → `analisar(..., criar_cliente=...)` substitui o cliente da API.
- `analise/config_ia.py` e `src/config/configIa.js` → `IA_ENV_FILE` aponta para outro
  arquivo `.env`, isolando a configuração de IA da máquina do usuário.
- `src/server/app.js` → `criarServidor(servicos)` substitui a ponte com o script.
- `src/server/analiseExterna.js` → `rodarScript(args, { script, python })` aponta para
  outro script ou interpretador.

## Convenções

**Idioma.** Código, comentários, nomes e mensagens de erro em **português do Brasil**, nas
duas linguagens. As chaves dos arquivos JSON e da API são snake_case em português
(`valor_atual`, `data_vencimento`, `resultado_pct`) — são contrato entre Python, Node,
front-end e o histórico já gravado em disco; **não renomeie**. Python usa snake_case;
JavaScript usa camelCase para funções e variáveis.

**Datas.** Sempre `AAAA-MM-DD`. No Python, `datetime.date`. No Node, use
`src/util/datas.js`, que trabalha em UTC — nunca `new Date(string)` para datas civis, o
fuso local desloca o dia.

**Erros.** Classes próprias, para que a camada acima distinga os casos:
`ValidacaoError` (Node, carteira), `CarteiraError` e `IAIndisponivel` (Python).
Falha de rede nunca deve derrubar o relatório: devolva um dicionário com a chave `erro` e
siga em frente (veja `market.cotacao`).

**Sem frameworks.** O Node usa só `http` e `fetch` embutidos e **não tem dependências de
produção** — não adicione Express, dotenv ou axios. O Python usa `requests`, `anthropic`
e `python-dotenv`, todos já em `requirements.txt`. Só acrescente uma dependência se não
houver equivalente embutido — e diga por quê.

## Testes

Duas suítes, uma por metade. Nenhuma toca a rede.

**Jest (`test/*.test.js`)** — aplicação Node. ESM nativo, sem Babel; roda com
`--experimental-vm-modules` (já embutido no script do npm). Em ESM, o objeto `jest` vem de
`import { jest } from "@jest/globals"` — `describe`/`test`/`expect` são globais.
Helpers em `test/helpers/ambiente.js`: `dataDirTemporario()` isola o disco via
`PORTFOLIO_DATA_DIR`, `comEnv()` isola variáveis de ambiente (devolve um restaurador —
chame-o num `finally`), `envIaTemporario()` isola a configuração de IA num `.env`
temporário apontado por `IA_ENV_FILE`, `gravarAnalise()` simula o que o Python grava.
A ponte com o Python é testada disparando **scripts Python mínimos** escritos num
diretório temporário, nunca o script real.

**pytest (`tests_analise/`)** — motor de análise. Fixtures em `conftest.py`: `env_ia` é
**autouse** e aponta `IA_ENV_FILE` para um `.env` temporário (sem isso os testes leriam a
chave e o modelo reais do usuário) — ela devolve um escritor de variáveis; `dados_temp`
aponta `PORTFOLIO_DATA_DIR` para um `tmp_path`; `rede` substitui `requests.get` por uma
tabela de rotas; `mercado_padrao` já traz os indicadores macro; `snapshot_exemplo` e
`ia_exemplo` alimentam relatório e fundamentos. Os testes do CLI rodam o script de verdade
em subprocesso, com a rede substituída por um `sitecustomize.py` temporário e um
`ia.env` próprio.

Cobertura Jest: ~97% de linhas. Ao mexer em `analise/` ou `src/core/`, mantenha o módulo
alterado coberto.

**Nenhum teste pode abrir o navegador.** `abrirNavegador` recebe o executor por parâmetro
(`{ executar }`) justamente para isso; o que se testa de verdade é `comandoNavegador`, que
é pura. Não chame `abrirNavegador` sem injetar um dublê.

## Cuidados específicos

**`data/` contém dados reais do usuário.** `portfolio.json`, `cache.json`,
`last_analysis.json` e `history/` são pessoais e estão no `.gitignore`. Nunca sobrescreva
esses arquivos ao testar — use `PORTFOLIO_DATA_DIR`, respeitado pelas duas linguagens.

**Chamada à IA.** Está em `analise/ai_insights.py` e usa o SDK oficial Python da Anthropic:
`output_config` com `effort` e `format: {"type": "json_schema", "schema": SCHEMA}`, a
ferramenta de servidor `web_search_20260209`, e — só nas famílias Opus 5 / Fable 5 —
`client.beta.messages.create` com `betas=["server-side-fallback-2026-07-01"]` e
`fallbacks="default"`. Enviar `fallbacks` para outros modelos devolve 400: a checagem está
em `config_ia.suporta_fallback()`. Trate `stop_reason` (`refusal`, `max_tokens`) antes de
ler o conteúdo.

**Nada de modelo ou esforço fixo no código.** Toda a configuração da IA sai do `.env`, lido
por `analise/config_ia.py` (Python) e `src/config/configIa.js` (Node) — os dois com as
mesmas regras, porque leem o **mesmo** arquivo:

- o `.env` tem **precedência** sobre variáveis já presentes no ambiente (o inverso de
  `carregarEnv`, que só preenche o que falta em `process.env`);
- `IA_PROVEDOR` escolhe o bloco, e o nome vira o prefixo em maiúsculas: `kimi` lê
  `KIMI_MODEL`, `KIMI_EFFORT`, `KIMI_BASE_URL`, `KIMI_FALLBACK`, `KIMI_BUSCA_WEB`,
  `KIMI_MAX_TOKENS`. Um novo provedor compatível com a API da Anthropic entra só no `.env`;
- `<PREFIXO>MODEL` e `<PREFIXO>EFFORT` são **obrigatórios** — sem padrão em lugar nenhum.
  `EFFORT=nenhum` omite o campo (é o caso do Kimi, que não o usa);
- `<PREFIXO>ORIGEM_CHAVE` declara de onde vem a credencial: `arquivo` lê **somente**
  `<PREFIXO>API_KEY` do `.env` e falha se faltar; `ambiente` lê **somente** a variável de
  ambiente cujo nome está em `<PREFIXO>VARIAVEL_CHAVE`. Não misture as duas fontes.

Ao acrescentar uma opção de provedor, ela entra em `configuracao()` (Python) e, se a
interface precisar dela, em `configuracaoIa()` (Node) — nunca como constante no meio da
chamada. O Node **não** devolve a chave: `conferirChave()` só verifica a presença.

**Os números agregados não vêm do modelo.** A IA devolve as fichas por ativo (P/VP, DY,
segmento, gestora); as médias ponderadas, a renda estimada e as concentrações são
calculadas em `analise/fundamentals.py`. Mantenha essa divisão: pedir totais ao modelo
introduz erro aritmético.

**Uma execução sem IA herda a leitura anterior.** `persistir` grava por cima do registro
do dia, então `--sem-ia` (o botão "Atualizar cotações") ou uma tentativa que falhou
apagariam as fichas já salvas — e com elas a alocação por classificação, segmento e
gestora, além da tela de análise. `runner._reaproveitar_ia` herda o bloco `ia` da última
análise em disco, de qualquer data, e `fundamentals` recalcula pesos e valores com o
snapshot de agora; a origem vai em `ia_reaproveitada_de` (o `_meta.gerado_em` herdado).
Interface e relatórios marcam essa data — nunca apresente a leitura herdada como se fosse
desta execução.

**O nome da gestora é normalizado sem IA.** O modelo escreve a mesma casa de formas
diferentes a cada execução ("XP Asset Management (XP Vista)" e "XP Vista Asset
Management (administração BTG Pactual)"), o que quebraria a concentração real em duas
linhas. `analise/gestoras.py` reduz cada nome a uma chave — sem parêntese explicativo,
sem acento e sem os termos de razão social — e junta as chaves em que uma é prefixo da
outra; `fundamentals` reescreve a ficha com o rótulo canônico antes de agrupar. Não peça
essa unificação ao modelo: a saída dele não é estável entre execuções.

**Marcação a mercado de CDB é estimativa.** `analise/fixed_income.py` projeta o CDI de hoje
sobre todo o período decorrido, capitaliza em dias úteis (base 252) e aplica o IR
regressivo. Não apresente esses valores como oficiais — o rodapé do relatório já avisa.

**Front-end.** `web/` é HTML, CSS e JS puros, servidos como estáticos em `/static/`.
Não introduza build step, bundler ou framework. O JS usa **módulos ESM nativos do
navegador**: `web/app.js` é o ponto de entrada (`<script type="module">`) e só orquestra —
carrega da API, guarda o último resultado e chama os módulos de `web/js/`, um por tela
(`visaoGeral`, `alocacao`, `posicoes`, `analiseIa`, `historico`, `configuracoes`) mais três
de apoio (`formato`, `api`, `icones`, `navegacao`). Nenhum cálculo mora no front. As chaves
consumidas são as mesmas do JSON que o Python produz — se mudar o formato de um snapshot,
atualize o front junto.

A interface tem cinco telas trocadas pelo hash da URL (`#posicoes`, `#historico`, …), sem
recarregar a página e sem roteador. Ícones são SVG de traço em `web/js/icones.js` — nunca
glifos de texto ou emoji. O gráfico do histórico é SVG desenhado à mão em
`web/js/historico.js`; não adicione biblioteca de gráfico.

**Uma base e uma régua na alocação.** Os três recortes (`por_classificacao`,
`por_segmento`, `por_gestora`) têm `peso_pct` sobre o **total da carteira**, não sobre o
total das fichas — é a mesma base da alocação por classe, e por isso `fundamentals`
devolve também `nao_coberto`, a parte sem ficha (renda fixa). O limite que vale em toda a
interface é o `alerta_concentracao_pct` do cadastro, publicado no snapshot como
`limite_concentracao_pct` e desenhado como traço na barra. Não reintroduza um limite fixo
no front. O recorte por emissor de renda fixa vem de `snapshot.emissores_renda_fixa`
(calculado em `analysis.py`, com o consumo do teto do FGC), porque `fundamentals` só
percorre fichas de renda variável.

**Localizar o Python.** `src/server/analiseExterna.js` usa `PYTHON_BIN` quando definido,
senão `python` no Windows e `python3` nos demais. Um `ENOENT` no spawn vira uma mensagem
explicando isso — mantenha esse tratamento.

**Segurança.** O servidor ouve só em `127.0.0.1`; não exponha na rede. `servirArquivo()`
tem proteção contra travessia de diretório — há teste cobrindo isso; não a remova.
Credenciais só via `.env`, nunca no código nem em logs.

## Aviso do domínio

Este material é informativo e não constitui recomendação de investimento. O prompt do
sistema instrui o modelo a descrever cenários e riscos sem recomendar compra ou venda de
forma imperativa — preserve essa instrução ao editar `SYSTEM_PROMPT`.

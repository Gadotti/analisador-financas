# CLAUDE.md

Orientações para o Claude Code trabalhar neste repositório.

## O que é

Sistema local de análise de carteira de investimentos brasileira (FIIs, ações da B3, renda
fixa bancária — CDB, LCI e LCA — e títulos do Tesouro Direto).
Roda inteiramente na máquina do usuário: dados em arquivos JSON, servidor web ouvindo em
`127.0.0.1` por padrão (a variável `HOST` muda o endereço, para expor na rede).

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
python scripts/analisar.py --previa-telegram   # a mensagem de hoje, sem enviar
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
| `data/execucoes.json` | Python (`analise/runner.py`) | Node e Python |
| `data/cache.json` | Python (`analise/cache.py`) | Python |

`history/` e `execucoes.json` respondem a perguntas diferentes e por isso convivem: o
arquivo do dia guarda o **estado** (é sobrescrito a cada rodada, e o gráfico do histórico
lê um ponto por dia), enquanto `execucoes.json` guarda o **que aconteceu em cada rodada** —
uma linha por execução, nunca sobrescrita, com status, erro da API, modelo, esforço,
buscas e duração. Sem ele, uma falha desaparecia assim que a execução seguinte gravava o
arquivo do dia por cima. Quem monta a linha é `runner._registro_execucao`; a tela de
Histórico lista o log e o `_status_execucao` classifica cada rodada em `sucesso`,
`sem_ia`, `erro` ou `erro_recuperado` (falhou, mas a leitura anterior foi mantida).

O log é uma janela deslizante: `config["max_execucoes"]` (30 por padrão, editável em
Configurações) é o teto, e `_anexar_execucao` descarta as linhas mais antigas ao gravar a
nova. O corte é do lado de quem **escreve** — o Node só lê o arquivo já cortado.

Por isso `analise/portfolio.py` é **somente leitura** — sem CRUD, sem gravação, sem
migração de formato. Se precisar de uma nova regra de validação de posição, ela vai em
`src/core/portfolio.js` (renda variável e CRUD), `src/core/rendaFixa.js` (papel bancário e
Tesouro) ou `src/core/validacao.js` (conversão e mensagem de erro de um campo).

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

`tests_analise/test_relevancia.py` cobre a seleção da mensagem curta injetando
`hoje`: é assim que se testa "no marco de 15 dias fala, no 14º cala" e o rodízio do
ativo do dia sem depender da data em que a suíte roda.
`test/web/configuracoes.test.js` trava o contrato entre as metades da tela —
coleta o formulário e passa o resultado pelo `atualizarConfig` de verdade, para que
um campo declarado só numa das tabelas apareça como falha em vez de ser descartado
em silêncio. `test/web/painelPosicao.test.js` faz o mesmo pelo cadastro: confere que
as opções que o painel oferece são exatamente as que `REGRAS` aceita e que o que o
formulário coleta passa por `normalizar` — uma opção só na tela viraria erro de
validação na cara do usuário, e um tipo novo que o coletor não conhece gravaria a
posição sem o campo que só ele tem.

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

**Uma função por natureza de ativo.** `analise/posicoes.py` marca cada posição a valor de
hoje (`variavel`, `renda_fixa`, `dados_do_tesouro`) e devolve sempre o mesmo formato de
dicionário; `analise/analysis.py` só soma, pesa, ordena e gera alertas, sem saber de onde
veio cada número. Uma fonte nova entra em `posicoes.py`, não em `consolidar`.

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

**Papel bancário vale a curva; Tesouro vale o mercado.** São dois regimes, e a diferença é
de fato, não de gosto: não existe mercado secundário de CDB, LCI ou LCA para pessoa física,
então a curva é o que o banco paga; o título público tem preço de revenda publicado todo
pregão.

- **CDB, LCI e LCA** — `analise/fixed_income.valorizar` projeta o CDI de hoje sobre todo o
  período decorrido, capitaliza em dias úteis (base 252) e aplica o IR regressivo. É
  estimativa.
- **Tesouro** — a curva é calculada do mesmo jeito, mas `fixed_income.marcar_a_mercado`
  troca o valor por `quantidade × PU de venda` do último pregão. A curva não é jogada
  fora: fica em `valor_na_curva`, que é o que o papel rende para quem carrega até o fim.
  `valor_atual` — e portanto os totais, a alocação e os pesos — é o valor de mercado.

O IR e a custódia saem de `_liquidar`, chamado pelos dois caminhos: a alíquota incide
sobre o ganho de cada regime, não sobre o do outro.

**A isenção da LCI e da LCA é regime de liquidação, não campo de cadastro.** Quem paga IR e
quem paga custódia à B3 está declarado numa tabela só, `fixed_income.REGIME`, ao lado do
cálculo que a aplica — `_liquidar` e `_juros_recebidos` leem de lá, e `_custodia_b3` não
volta a comparar `tipo != "tesouro"`. Um tipo novo de renda fixa é uma linha nova ali.

A isenção precisa **aparecer** em toda saída que mostra uma taxa, porque sem ela 95% do CDI
parece pior que um CDB de 100%: `valorizar` publica `isento_ir` na posição, e o relatório, a
tabela de posições, o formulário e o prompt da IA dizem "isento de IR". Não recalcule a
isenção a partir do tipo em cada consumidor — leia o campo.

**A taxa do Tesouro não é digitada.** `analise/tesouro_direto.py` lê o CSV "Taxas dos
Títulos Ofertados pelo Tesouro Direto" e resolve duas coisas por título:

| Precisa de | Coluna | Quando |
|---|---|---|
| Taxa travada na compra | `Taxa Compra Manha` no pregão da `data_aplicacao` | uma vez por título |
| Preço de revenda hoje | `PU Venda Manha` no último pregão | uma vez por execução |

**Os rótulos do arquivo são da ótica do investidor**, conforme os metadados oficiais:
"Compra" é a ponta em que ele compra, "Venda" é onde revende ao Tesouro. Trocá-las inverte
o resultado — há teste travando as duas. A quantidade de títulos também não é pedida no
cadastro: sai de `valor_inicial ÷ PU de compra`, que a mesma consulta já traz.

O arquivo tem 14 MB e vem ordenado do pregão mais novo para o mais antigo. `cotacoes()`
para de ler na primeira data diferente e fecha a conexão — o servidor responde 206 ao
cabeçalho `Range` e manda o corpo inteiro assim mesmo, então o corte é do lado do cliente.
`taxas_na_compra()` precisa varrer tudo, mas pregão fechado não muda: o resultado vai ao
cache com `SEM_EXPIRAR`, e a chave é o título comprado, não a posição.

Se a busca falhar e não houver taxa no cadastro, a posição entra pelo valor aplicado com
`erro_cotacao` — mesmo tratamento da renda variável sem cotação. Uma taxa informada no
cadastro sempre vence a buscada: é a que está no extrato da corretora.

**Quatro tipos de renda fixa, um esqueleto só.** `cdb`, `lci`, `lca` e `tesouro`
compartilham valor aplicado, indexador, taxa, prazo e forma de pagamento dos juros. Divergem
no que a tabela `REGRAS` de `src/core/rendaFixa.js` declara (e `analise/portfolio.py`
espelha):

| | CDB | LCI e LCA | Tesouro |
|---|---|---|---|
| Indexadores | CDI, PRE, IPCA | CDI, PRE, IPCA | SELIC, PRE, IPCA |
| Cupom | `vencimento` ou `mensal` | `vencimento`, `mensal` ou `semestral` | `vencimento` ou `semestral` |
| Emissor | o banco, com teto do FGC | o banco, com teto do FGC | Tesouro Nacional, sem FGC |
| Taxa no cadastro | obrigatória | obrigatória | opcional (buscada) |
| IR no resgate | regressivo | isento | regressivo |

CDB, LCI e LCA saem da mesma fábrica, `papelBancario(sigla, pagamentos)`: do ponto de vista
do cadastro são o mesmo papel — um banco emissor, uma taxa contratada e um prazo —, e o que
os separa é a sigla que nomeia a posição e o cupom oferecido. Não copie o bloco do CDB para
declarar um quarto papel bancário. A carência legal da LCI e da LCA é o motivo de a
interface não oferecer a elas a caixa de liquidez diária, como já não a oferece ao Tesouro;
o **prazo mínimo não é validado**, porque a carência mudou com o tempo e recusar um papel
antigo, já comprado, seria errado.

Tesouro Selic é a exceção do cupom: paga tudo no vencimento, e `REGRAS.tesouro.conferir`
recusa a combinação — ela não existe no Tesouro Direto e nunca teria preço para casar.

O CDI é multiplicativo (110% do CDI); a Selic é aditiva (Selic + 0,09% a.a.) — veja
`_taxa_efetiva`. Só o Tesouro paga custódia à B3 (0,20% a.a., isenta na primeira faixa em
Tesouro Selic), descontada do `valor_liquido` em `_custodia_b3`. O nome padrão de um título
sai de `REGRAS[tipo].nomePadrao` — a sigla mais o banco e a taxa no papel bancário,
`nomeTesouro()` no padrão em que o Tesouro Direto o publica ("Tesouro IPCA+ 2029 com Juros
Semestrais"); o usuário pode sobrescrever o do Tesouro.

Ao acrescentar um quinto tipo de renda fixa, ele entra em `REGRAS`, em `fixed_income.REGIME`,
em `INTERVALO_CUPOM` e, se for título público, em `tesouro_direto.TIPO_TITULO` — não em mais
um `if` espalhado pelo relatório e pelo front.

**Título com cupom não capitaliza.** No modo `mensal` ou `semestral` cada
aniversário da aplicação — ajustado para o dia útil seguinte — paga os juros do período e o
principal segue intacto, com o IR retido em cada cupom pelo prazo decorrido até ele. Por
isso `valor_atual` e `resultado` medem só o que continua aplicado; os cupons já sacados
saíram da carteira e vivem em `juros_recebidos_*`, com o acumulado dos dois em
`resultado_total`. Não some cupom em `valor_atual`: os totais do snapshot são a soma dos
`valor_atual` das posições, e a carteira deixaria de fechar.

**O FGC é do banco, não do país.** `emissores_renda_fixa` lista todo emissor de renda fixa,
mas só o papel bancário consome teto do FGC (`analysis.TIPOS_COM_FGC`, que é a própria
`portfolio.TIPOS_BANCARIOS` para não existir uma segunda relação capaz de divergir dela); a
linha do Tesouro Nacional vem com `fgc_limite: None` e `garantia: "Tesouro Nacional"`, e
nunca dispara o alerta de teto estourado. O teto é **por CPF/instituição, não por papel**:
o CDB, a LCI e a LCA do mesmo banco somam num consumo só, que é o que `_exposicao_por_emissor`
já fazia ao agrupar por emissor. O alerta de concentração por posição, esse sim, vale para
qualquer ativo.

**Front-end.** `web/` é HTML, CSS e JS puros, servidos como estáticos em `/static/`.
Não introduza build step, bundler ou framework. O JS usa **módulos ESM nativos do
navegador**: `web/app.js` é o ponto de entrada (`<script type="module">`) e só orquestra —
carrega da API, guarda o último resultado e chama os módulos de `web/js/`, um por tela
(`visaoGeral`, `alocacao`, `posicoes`, `analiseIa`, `equivalencia`, `historico`,
`configuracoes`), mais `painelPosicao`, que é só o formulário de cadastro, e os de apoio
(`formato`, `api`, `icones`, `alertas`, `navegacao`). Nenhum cálculo da carteira mora no
front — a única conta ali é a da tela de equivalência, e o porquê está em "Cuidados
específicos". As chaves consumidas são as
mesmas do JSON que o Python produz — se mudar o formato de um snapshot, atualize o front
junto.

**Campo de formulário é componente do sistema, não do cartão.** Todo número,
seletor, caixa de marcar e área de texto usa `.campo` dentro de uma `.grade-form`
(`style.css`): rótulo acima em micro maiúsculo, controle de 40px, foco em âmbar.
Um campo novo — em qualquer tela — herda isso; não crie uma classe de campo para
um cartão só. O "Máx. de tokens" e o "Esforço" do cartão de IA são a referência, e
os limiares do Telegram passaram a segui-la depois de terem nascido com um
componente próprio, menor e diferente de todo o resto. Precisa ajustar o
**arranjo**, e não o controle? Aí sim entra um modificador de contêiner — como
`.campo-largo`, que já existia, ou `.grade-form-compacta`, que limita a largura da
coluna numa linha de poucos campos.

Ao acrescentar CSS, **procure o nome da classe antes** (`grep -rn "nome" web/`).
Um nome genérico reusado por acidente vence por cascata e quebra a tela alheia: a
chave do Telegram nasceu como `.trilho`, o mesmo nome da barra de alocação, e
transformou toda barra de peso da carteira numa pílula de 30px em Visão geral e
em Posições. Há teste travando esse caso.

**A tabela de posições declara as colunas, não as escreve.** `web/js/posicoes.js` quebra a
listagem em um grupo por classe de ativo, e cada classe traz o seu próprio array de colunas
(`{ rotulo, num, mono, celula(item) }`) — um CDB não tem P/VP, um FII não tem vencimento.
Todas terminam nas mesmas quatro colunas de `COLUNAS_COMUNS` (valor, resultado, peso e
ações), e é por isso que os grupos continuam numa tabela só, com os números alinhados de
ponta a ponta. Uma classe nova entra em `GRUPOS` com o seu array; uma informação nova entra
como coluna ou como linha de apoio de uma célula (`celula(principal, ...apoios)`), nunca
como um `if` dentro do laço que desenha as linhas. Busca, ordenação e recolhimento são
estado local do módulo — o `app.js` não os conhece.

**O painel de cadastro declara os campos de cada tipo, e o HTML só os marca.** Em
`web/js/painelPosicao.js`, `FORMULARIO_RF` diz por tipo quais são as opções de indexador e
de cupom, quais campos opcionais ele usa (`banco`, `nome`, `liquidez`) e qual é a dica sob o
rótulo da taxa; no HTML, esses campos levam só `data-campo="banco"`. É a mesma tabela que
decide o que **aparece** e o que é **coletado** — antes eram uma classe por tipo
(`.campo-cdb`, `.campo-tesouro`) mais um `if` no coletor, duas listas para uma decisão só, e
um tipo novo esquecido em qualquer das duas gravava a posição sem o campo. Um tipo novo é
uma linha em `FORMULARIO_RF`, e o `.campo` correspondente já existe no HTML.

A interface tem seis telas trocadas pelo hash da URL (`#posicoes`, `#equivalencia`, …), sem
recarregar a página e sem roteador. Ícones são SVG de traço em `web/js/icones.js` — nunca
glifos de texto ou emoji. O gráfico do histórico é SVG desenhado à mão em
`web/js/historico.js`; não adicione biblioteca de gráfico.

**Uma base por regime, uma régua só na alocação.** Cada recorte pesa sobre o regime a que
os seus itens pertencem, e não sobre a carteira inteira — a divisão entre regimes é o que
o rosco de classes já mostra, logo acima. Os três recortes por ficha (`por_classificacao`,
`por_segmento`, `por_gestora`) têm `peso_pct` sobre o **total de renda variável**, e por
isso `nao_coberto` é a renda variável que a IA não leu (quase sempre zero), não mais a
renda fixa. O recorte por emissor vem de `snapshot.emissores_renda_fixa` (calculado em
`analysis.py`, com o consumo do teto do FGC, porque `fundamentals` só percorre fichas de
renda variável) e pesa sobre o **total de renda fixa** — um título já vencido sai do
recorte mas fica no total, então esses pesos podem somar menos de 100%.

As bases saem de `analysis._bases_concentracao` e vão no snapshot em
`bases_concentracao` (`carteira`, `renda_variavel`, `renda_fixa`); `fundamentals` lê a de
renda variável de lá e a republica em `valor_base_recortes`. O limite continua **um só**:
o `alerta_concentracao_pct` do cadastro, publicado como `limite_concentracao_pct` e
desenhado como traço na barra. Ele é lido **na base do recorte**, a mesma do peso que está
ao lado — 50% é metade da renda variável nos três recortes por ficha e metade da renda
fixa nos emissores. Não o reescale para a carteira: num regime que vale um terço dela, 50%
da carteira seriam 150% do recorte, o traço encostaria no fim da escala e nenhuma barra o
alcançaria. O alerta de concentração por posição (`analysis._gerar_alertas`) segue medindo
o mesmo limite sobre a carteira — são leituras diferentes da mesma régua, e é por isso que
a tela declara a base. Não reintroduza um limite fixo no front.

**A tela de equivalência é a única conta do front.** `web/js/equivalencia.js` converte a taxa
que o usuário digita — uma LCI ofertada em taxa líquida contra um CDB em taxa bruta — e por
isso responde a cada tecla, sem ida ao Python. A regra de negócio que ela usa não mora lá: as
alíquotas vêm de `snapshot.ir_renda_fixa`, publicado por `fixed_income.faixas_ir()`, a mesma
`TABELA_IR` que `_liquidar` aplica no resgate. Não escreva uma tabela de IR no front — sem a
chave no snapshot, o cartão troca a conta por um aviso. O que o módulo faz é dividir por
`1 - alíquota` (ou multiplicar), nas duas direções, sobre o CDI de `macro.cdi_anual_pct`.

Os quatro cartões de prazo são a resposta inteira **e** o seletor: o escolhido alimenta o
painel de cima, e os outros três continuam à vista, que era o ponto de comparar as alíquotas.
Eles são montados uma vez por snapshot (`montarFaixas`) e só têm os valores repintados
(`pintarFaixas`) — redesenhar o HTML a cada tecla tiraria o foco de quem navega pelo teclado.

**O quadro "Posição do mercado" aparece em duas telas.** A da equivalência precisa dele
porque o CDI é a base da conversão. Por isso `renderMacro` escreve em todo `[data-macro]` e
`[data-macro-quando]`, e não num id — para acrescentar o quadro a uma terceira tela basta
repetir a marcação, sem tocar no JS.

**A mensagem do Telegram é HTML, e o corte é por linha.** As duas mensagens moram em
`analise/mensagem.py` (`telegram`, o relatório inteiro, e `telegram_resumo`, o envio de
cada dia); `analise/report.py` ficou só com o relatório de terminal, e o que os dois
formatos compartilham — ícones, rótulos e `leitura_herdada` — está em `analise/formato.py`.
O Telegram aceita só um HTML
restrito e recusa a mensagem inteira com **400** se houver tag aberta, entidade partida ou
mais de 4096 caracteres — então todo texto vindo da IA ou do cadastro passa por
`formato.escapar_html`, e cada linha fecha as próprias tags. É essa
invariante que permite `_juntar_no_limite` descartar as **últimas linhas inteiras** quando
não couberem; nunca volte a cortar a string no meio (`mensagem[:4090]`), porque um `<i>`
aberto derruba o envio. O limite é contado em **unidades UTF-16** (`_unidades_utf16`) — o
relatório é cheio de emoji, e cada um fora do BMP vale 2. O rodapé com o aviso de que o
material não é recomendação fica fora do corte e é sempre mantido.

`notifier._conferir` levanta o `description` que a API devolveu ("chat not found",
"can't parse entities") em vez de `resp.raise_for_status()`: a mensagem dele traz a URL
chamada, e o **token do bot vai na URL** — ele apareceria no log e na tela do usuário.

**O envio de cada dia é o resumo, não o relatório.** `report.telegram` (o relatório
inteiro) continua existindo, mas só sob demanda — `--completo`, ou `?completo=1` na rota.
O envio automático manda a mensagem curta de `mensagem.telegram_resumo`, montada a partir
da seleção de **`analise/relevancia.py`**. São três responsabilidades separadas:

| Módulo | Responde |
|---|---|
| `analise/gatilhos.py` | quando cada bloco tem algo a dizer, e o que ele diz |
| `analise/relevancia.py` | junta, pontua, corta pelo orçamento e monta a seleção |
| `analise/mensagem.py` | como a seleção vira HTML do Telegram |

Não escreva HTML em `gatilhos` nem regra de seleção em `mensagem`. Um bloco devolver
lista vazia **é** o gatilho — não existe um `gatilho()` separado do `montar()`, seriam
duas funções para uma decisão só.

O princípio é *estado vive na interface, o Telegram carrega evento*. O estado da carteira
entra em **uma linha** (`_linha_estado`) só para dar escala; o resto da mensagem é o que
mudou. `notifier.enviar` nunca manda `disable_notification: true` — toda mensagem deste
sistema tem que tocar o aparelho, em qualquer situação.

**Interruptor e gatilho: é o gatilho que faz a mensagem variar.** Cada bloco tem um
`ativo` no cadastro (pode aparecer?) e um limiar (merece aparecer **hoje**?). Só o
interruptor daria uma mensagem configurável mas fixa; o limiar é o que deixa a maioria dos
blocos calada na maioria dos dias. **A seleção é função pura** do snapshot desta execução
mais o cadastro: não lê histórico, não guarda estado, não toca a rede — `hoje` é injetável
para os testes. Onde o limiar não serve, quem varia é o calendário:

- `_calendario_rf` fala nos **marcos** de dias que faltam (`marcos_dias`, 30/15/7/3/1 por
  padrão), e não numa janela: "faltam menos de 30 dias" citaria o mesmo vencimento trinta
  vezes seguidas, o marco o cita cinco vezes, em dias distintos.
- `_aprofundamento` escolhe o ativo do dia por `dia_do_ano % nº de fichas`, ordenadas por
  ticker — a ordem em que a IA devolve as fichas não é estável entre execuções, e sem o
  `sorted` o rodízio repetiria ou pularia ativos.
- `_resumo_ia` e `_semanal` saem do dia da semana (`dias_semana`, `dia_semana`).

`gatilhos.BLOCOS` é a tabela que declara **a ordem de leitura e o peso** de cada bloco. Um
bloco novo é uma linha nova ali, não um `if` no meio do montador — mesmo padrão de
`REGRAS` em `rendaFixa.js` e de `GRUPOS` em `web/js/posicoes.js`. A tela de Configurações
tem a sua própria tabela espelhada em `BLOCOS` de `web/js/configuracoes.js`, com os
rótulos.

**O corte é por relevância, a exibição é por bloco.** `_no_orcamento` aplica dois
critérios de propósito: **quem entra** é decidido pela relevância
(`peso do bloco × severidade × (1 + peso da posição)`), **quem vem antes** pela ordem da
tabela. Ordenar a exibição pela relevância embaralharia as posições em movimento com os
alertas. Por isso o `aprofundamento` tem o menor peso: é o enchimento do dia calmo e é o
primeiro a sair quando o dia é cheio. `_juntar_no_limite` fica como rede de segurança —
não é mais ele que decide o que cabe.

**Alerta em curso é uma linha, não um bloco.** Sem histórico não há como saber se um
alerta é novo. Os que ficam abaixo de `severidade_minima` (ou que não couberam no
orçamento) não desaparecem: `_em_curso` os conta, e a mensagem traz "3 alerta(s) em
curso". Repetir o texto inteiro de todos eles todo dia é justamente o que se quer evitar.

**Selic, CDI e IPCA são a única comparação com o passado.** Eles mudam poucas vezes por
ano e a mudança reprecifica a carteira inteira, então a mudança **é** a notícia. O valor
anterior sai de `runner._macro_anterior`, que aproveita a leitura de `ultima_analise()`
que `executar` já fazia para herdar as fichas de IA — **nenhum arquivo novo e nenhuma
leitura a mais**; `relevancia.macro_comparavel` guarda só os três indicadores no registro,
não o `macro` inteiro. Duas armadilhas travadas por teste:

- `market._ultimo_valor` devolve um **padrão embutido** com `fonte: "padrao"` quando o BCB
  não responde. `_valor_macro` recusa esse padrão dos dois lados da comparação — sem isso,
  uma falha de rede anunciaria uma mudança que não houve.
- Numa execução intradiária o "anterior" é a rodada anterior de **hoje**, e é essa a
  leitura desejada: a mudança é anunciada uma vez, na rodada em que apareceu.

**A configuração mora no cadastro, e é espelhada nas duas metades.** O bloco `telegram` de
`config` fica em `data/portfolio.json` — escrito pelo Node, lido pelo Python, como todo o
resto do arquivo. `TELEGRAM_PADRAO` existe nas duas metades
(`analise/portfolio.py` e `src/core/portfolio.js`) e **as duas tabelas precisam continuar
idênticas**: um campo acrescentado só de um lado é descartado em silêncio pelo mesclador
do outro. O mesclador é profundo de propósito (`telegram_do_cadastro` /
`telegramDoCadastro`): um espalhamento raso trocaria o padrão inteiro pelo bloco parcial
do arquivo, e um cadastro gravado antes de um limiar existir perderia esse limiar.

No Node, `campoTelegram` **deriva o tipo do próprio padrão** — padrão booleano exige
booleano, numérico exige número, lista exige lista de inteiros — para que não exista uma
segunda tabela de tipos capaz de divergir da primeira. `MAXIMO_TELEGRAM` guarda os tetos;
um `dia_semana: 7` aceito desligaria o bloco semanal em silêncio.

**A tela dos limiares é recolhível, um bloco por linha.** Onze blocos com até três
limiares cada não cabem abertos sem encolher os campos abaixo do padrão do
sistema. Cada bloco é um `<details>` — o mesmo idioma nativo dos alertas e do
contexto de mercado, sem JS — com a caixa de marcar (entra ou não na mensagem) e,
à direita, na mesma linha, o **resumo dos limiares**: "limiar 3% · peso mín. 3% ·
máx. 3", montado por `resumoDoBloco` a partir dos próprios campos. Sem o resumo, a
dobra esconderia os valores e obrigaria a abrir bloco por bloco para conferir um
número; um ouvinte de `input` o mantém em dia enquanto se digita.

Recolhido, o bloco tem **exatamente os 40px de um controle de `.campo`** — 38px de
`min-height` no `summary` mais as duas bordas —, para a lista alinhar com o campo
logo acima dela e com o resto da tela. É `min-height`, e não espaçamento vertical:
a altura da linha do nome tem fração, e somar padding nunca fecharia em 40
redondo. Centrar o conteúdo dentro dela dá, de graça, um alvo de clique da altura
inteira da linha.

O bloco aberto cresce **na própria célula do grid**, e é para isso que serve o
`align-items: start` da `.grade-blocos`. Não devolva o `grid-column: 1 / -1` que
já esteve ali: o cartão saltava para a largura da tela e reordenava os vizinhos
sob o cursor de quem tinha acabado de clicar. Por isso são duas colunas e não
três — com ~520px de linha, os limiares de um bloco cabem lado a lado e a dobra
cresce uma fileira de campos em vez de três. Só `dias_semana` leva `campo-largo`.

O `name` compartilhado dos `<details>` faz do conjunto um acordeão exclusivo, sem
JS; recolher não perde nada, porque os campos seguem no DOM e `coletarConfig` os
lê fechados. A caixa de marcar é **irmã** do `<details>`, não filha do
`<summary>`: dentro dele, clicar na caixa também abriria a dobra.

**A prévia é o que torna os limiares calibráveis.** `--previa-telegram` devolve a mensagem
que *seria* enviada hoje sem enviar nada, e o botão da tela de Configurações a exibe. O
texto é montado pelo Python e o front só o mostra — a regra de "nenhum cálculo da carteira
no front" continua valendo. Sem a prévia, ajustar um limiar seria adivinhação.

**`ultimo_pagamento` é calendário, não histórico.** `fixed_income._juros_recebidos` já
calculava as datas dos cupons pagos; expor a última permite anunciar "cupom creditado
hoje" sem consultar execução anterior nenhuma. É o único campo novo que a mensagem curta
exigiu.

**Localizar o Python.** `src/server/analiseExterna.js` usa `PYTHON_BIN` quando definido,
senão `python` no Windows e `python3` nos demais. Um `ENOENT` no spawn vira uma mensagem
explicando isso — mantenha esse tratamento.

**Segurança.** O servidor ouve em `127.0.0.1` por padrão; a variável de ambiente `HOST`
muda o endereço — é o que o `Dockerfile` usa (`0.0.0.0`, para o `docker-compose.yml`
publicar a porta). `servirArquivo()` tem proteção contra travessia de diretório — há teste
cobrindo isso; não a remova. Credenciais só via `.env`, nunca no código nem em logs.
Isso vale também para teste: token, chave ou credencial usada como fixture (ex.:
`TELEGRAM_BOT_TOKEN` em `test_notifier.py`) é sempre um valor falso e obviamente inválido
("123456789:TESTE-FAKE-TOKEN"), nunca uma credencial real colada durante o
desenvolvimento — mesmo que o serviço nunca seja chamado de verdade no teste.

**Login único, sem framework.** A interface web exige autenticação — não há dado nem rota
anônima, o login só existe para liberar o acesso à ferramenta, e a carteira continua única
e sem segregação por usuário. Sem dependência de produção nenhuma (nada de bcrypt,
jsonwebtoken, cookie-parser ou express-rate-limit): `src/core/authService.js` faz o hash da
senha com `scrypt` e assina o token de sessão com HMAC-SHA256, os dois só com o módulo
`crypto` nativo do Node — um JWT mínimo, sem estado guardado no servidor.
`node scripts/criarLogin.js` grava usuário, hash da senha e o segredo de sessão em
`AUTH_USUARIO`, `AUTH_SENHA_HASH` e `AUTH_SESSAO_SEGREDO` no `.env` (`AUTH_ENV_FILE`
redireciona o arquivo, mesmo papel de `IA_ENV_FILE` — é como os testes isolam); nunca edite
essas três à mão. Diferente do fail-fast de outras configurações, **o servidor sobe do
mesmo jeito sem essas variáveis** — mesmo padrão do ShadowRadar: sem cookie válido, `GET /`
cai na tela de login e a API responde 401 normalmente; só a tentativa de login em si falha,
com a mensagem de `authConfig.js` apontando para o script (`iniciar()` imprime "Login: não
configurado" no terminal, ao lado do status de IA e Telegram, mas não recusa a porta).

Em `src/server/app.js`, a ordem de registro das rotas é o que decide o que é público: login
(`GET /login`, `POST /api/auth/login`, `POST /api/auth/logout`) e os arquivos estáticos em
`/static/` (só código, sem dado da carteira) vêm antes do gate; a partir dali, `GET /` sem
sessão redireciona (302) para `/login`, e qualquer outra rota `/api/*` sem sessão válida
responde 401. `src/server/limitadorLogin.js` é o freio contra força bruta (10 tentativas por
IP a cada 15 minutos, só em memória) que um framework daria de graça. O cookie de sessão é
`HttpOnly`, `SameSite=Strict` e dura 30 dias (`authService.SESSAO_MS`); como o token é
stateless, o logout só apaga o cookie do navegador — o token em si continua válido até
expirar, e é assim que o ShadowRadar também faz.

**Docker.** A imagem é publicada em `ghcr.io/gadotti/analisador-financas` pelo workflow
`.github/workflows/release.yml`, disparado por tag `v*.*.*` — mesmo padrão do
ShadowRadar: `release.py` empacota o zip de distribuição (lendo a versão de `version.js`)
e o workflow builda e publica a imagem a partir do mesmo `Dockerfile`. O
`docker-compose.yml` espera um `.env` de verdade montado em `/app/.env` (não
`environment:` nem `env_file:`), porque `ORIGEM_CHAVE=arquivo` lê a chave só do arquivo —
ver a seção de configuração de IA acima.

## Aviso do domínio

Este material é informativo e não constitui recomendação de investimento. O prompt do
sistema instrui o modelo a descrever cenários e riscos sem recomendar compra ou venda de
forma imperativa — preserve essa instrução ao editar `SYSTEM_PROMPT`.

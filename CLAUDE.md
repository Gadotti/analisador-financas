# CLAUDE.md

Orientações para o Claude Code trabalhar neste repositório.

## O que é

Sistema local de análise de carteira de investimentos brasileira (FIIs, ações da B3, CDBs e
títulos do Tesouro Direto).
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

Por isso `analise/portfolio.py` é **somente leitura** — sem CRUD, sem gravação, sem
migração de formato. Se precisar de uma nova regra de validação de posição, ela vai em
`src/core/portfolio.js` (renda variável e CRUD), `src/core/rendaFixa.js` (CDB e Tesouro) ou
`src/core/validacao.js` (conversão e mensagem de erro de um campo).

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

**CDB vale a curva; Tesouro vale o mercado.** São dois regimes, e a diferença é de fato,
não de gosto: não existe mercado secundário de CDB para pessoa física, então a curva é o
que o banco paga; o título público tem preço de revenda publicado todo pregão.

- **CDB** — `analise/fixed_income.valorizar` projeta o CDI de hoje sobre todo o período
  decorrido, capitaliza em dias úteis (base 252) e aplica o IR regressivo. É estimativa.
- **Tesouro** — a curva é calculada do mesmo jeito, mas `fixed_income.marcar_a_mercado`
  troca o valor por `quantidade × PU de venda` do último pregão. A curva não é jogada
  fora: fica em `valor_na_curva`, que é o que o papel rende para quem carrega até o fim.
  `valor_atual` — e portanto os totais, a alocação e os pesos — é o valor de mercado.

O IR e a custódia saem de `_liquidar`, chamado pelos dois caminhos: a alíquota incide
sobre o ganho de cada regime, não sobre o do outro.

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

**Dois tipos de renda fixa, um esqueleto só.** `cdb` e `tesouro` compartilham valor
aplicado, indexador, taxa, prazo e forma de pagamento dos juros. Divergem em três pontos,
declarados na tabela `REGRAS` de `src/core/rendaFixa.js` (e espelhados em
`analise/portfolio.py`):

| | CDB | Tesouro |
|---|---|---|
| Indexadores | CDI, PRE, IPCA | SELIC, PRE, IPCA |
| Cupom | `vencimento` ou `mensal` | `vencimento` ou `semestral` |
| Emissor | o banco, com teto do FGC | Tesouro Nacional, sem FGC |
| Taxa no cadastro | obrigatória | opcional (buscada) |

Tesouro Selic é a exceção do cupom: paga tudo no vencimento, e `REGRAS.tesouro.conferir`
recusa a combinação — ela não existe no Tesouro Direto e nunca teria preço para casar.

O CDI é multiplicativo (110% do CDI); a Selic é aditiva (Selic + 0,09% a.a.) — veja
`_taxa_efetiva`. Só o Tesouro paga custódia à B3 (0,20% a.a., isenta na primeira faixa em
Tesouro Selic), descontada do `valor_liquido` em `_custodia_b3`. O nome padrão de um título
sai de `nomeTesouro()` no padrão em que o Tesouro Direto o publica ("Tesouro IPCA+ 2029 com
Juros Semestrais"); o usuário pode sobrescrevê-lo.

Ao acrescentar um terceiro tipo de renda fixa, ele entra em `REGRAS`, em `INTERVALO_CUPOM`
e, se for título público, em `tesouro_direto.TIPO_TITULO` — não em mais um `if` espalhado
pelo relatório e pelo front.

**Título com cupom não capitaliza.** No modo `mensal` (CDB) ou `semestral` (Tesouro) cada
aniversário da aplicação — ajustado para o dia útil seguinte — paga os juros do período e o
principal segue intacto, com o IR retido em cada cupom pelo prazo decorrido até ele. Por
isso `valor_atual` e `resultado` medem só o que continua aplicado; os cupons já sacados
saíram da carteira e vivem em `juros_recebidos_*`, com o acumulado dos dois em
`resultado_total`. Não some cupom em `valor_atual`: os totais do snapshot são a soma dos
`valor_atual` das posições, e a carteira deixaria de fechar.

**O FGC é do banco, não do país.** `emissores_renda_fixa` lista todo emissor de renda fixa,
mas só o CDB consome teto do FGC (`analysis.TIPOS_COM_FGC`); a linha do Tesouro Nacional vem
com `fgc_limite: None` e `garantia: "Tesouro Nacional"`, e nunca dispara o alerta de teto
estourado. O alerta de concentração por posição, esse sim, vale para qualquer ativo.

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

**A tabela de posições declara as colunas, não as escreve.** `web/js/posicoes.js` quebra a
listagem em um grupo por classe de ativo, e cada classe traz o seu próprio array de colunas
(`{ rotulo, num, mono, celula(item) }`) — um CDB não tem P/VP, um FII não tem vencimento.
Todas terminam nas mesmas quatro colunas de `COLUNAS_COMUNS` (valor, resultado, peso e
ações), e é por isso que os grupos continuam numa tabela só, com os números alinhados de
ponta a ponta. Uma classe nova entra em `GRUPOS` com o seu array; uma informação nova entra
como coluna ou como linha de apoio de uma célula (`celula(principal, ...apoios)`), nunca
como um `if` dentro do laço que desenha as linhas. Busca, ordenação e recolhimento são
estado local do módulo — o `app.js` não os conhece.

A interface tem seis telas trocadas pelo hash da URL (`#posicoes`, `#equivalencia`, …), sem
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

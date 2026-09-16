# Analisador de Finanças

Sistema local de acompanhamento e análise de carteira de investimentos — **FIIs, ações,
renda fixa bancária (CDB, LCI e LCA) e Tesouro Direto**.
Cotações reais da B3, marcação a mercado de renda fixa, alertas automáticos e uma leitura
diária de mercado gerada por IA com busca web.

Tudo roda na sua máquina: os dados ficam em arquivos JSON locais e o servidor da interface
escuta em `127.0.0.1` por padrão (a variável `HOST` muda o endereço, para acessar pela rede).

O projeto tem duas metades, cada uma na linguagem que lhe cai melhor:

| Parte | Linguagem | Papel |
|---|---|---|
| **Análise** (`analise/` + `scripts/analisar.py`) | Python | Cotações, marcação a mercado, alertas, IA e Telegram |
| **Aplicação** (`src/` + `web/`) | Node.js | Cadastro da carteira, interface web e API local |

A interface **dispara o script Python** quando você aperta o botão; o mesmo script roda
sozinho pelo terminal.

---

## Instalação

Requer **Python 3.10+** e **Node.js 20.11+**.

```powershell
cd e:\Eduardo\Sistemas\analisador-financas
pip install -r requirements.txt
npm install
copy .env.example .env
node scripts/criarLogin.js
```

`criarLogin.js` pede um usuário e uma senha no terminal e grava o hash da senha em
`data/usuarios.json` — nunca a senha em texto puro, e nunca no `.env`. Aceita mais de um
usuário (rode o script de novo com outro nome para adicionar; com um nome já existente,
troca só a senha dele) — todos autenticam contra a mesma carteira, sem segregação nenhuma:
o login só existe para liberar o acesso à ferramenta. Sem nenhum usuário cadastrado, o
servidor sobe do mesmo jeito, mas nenhuma tela ou rota da API responde sem uma sessão
válida: qualquer acesso cai na tela de login, e o próprio login falha com uma mensagem
apontando para este script.

Edite o restante do `.env` conforme o que mais pretende usar. Fora o login, **nada é
obrigatório** — sem o bloco do provedor de IA o sistema continua calculando cotações,
rentabilidade, alocação e alertas normalmente; só a análise de mercado por IA fica
indisponível.

O `.env` é quem manda: o que estiver nele tem precedência sobre variáveis já definidas no
ambiente, e **nenhum modelo ou esforço é fixo no código**.

| Variável | Para quê |
|---|---|
| `IA_PROVEDOR` | Qual bloco de variáveis vale: `anthropic` (padrão) ou `kimi` |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Envio do relatório ao Telegram |
| `BRAPI_TOKEN` | Fonte alternativa de cotações |
| `PYTHON_BIN` | Interpretador Python que a interface deve chamar (útil com venv) |

O nome em `IA_PROVEDOR` vira o prefixo das variáveis do provedor (`anthropic` →
`ANTHROPIC_*`, `kimi` → `KIMI_*`). Cada bloco aceita:

| Variável | Para quê |
|---|---|
| `<P>_MODEL` | Modelo da análise. **Obrigatória** |
| `<P>_EFFORT` | Profundidade: `low`, `medium`, `high`, `xhigh`, `max` ou `nenhum` para não enviar o campo. **Obrigatória** |
| `<P>_ORIGEM_CHAVE` | Onde buscar a chave: `arquivo` (padrão) ou `ambiente` |
| `<P>_API_KEY` | A chave, quando a origem é `arquivo` — lida **somente** daqui |
| `<P>_VARIAVEL_CHAVE` | O **nome** da variável de ambiente que guarda a chave, quando a origem é `ambiente` |
| `<P>_BASE_URL` | Endereço da API, para provedores compatíveis com a API da Anthropic |
| `<P>_FALLBACK` | `auto` (pela família do modelo), `sim` ou `nao` |
| `<P>_BUSCA_WEB` | `sim` (padrão) ou `nao` — ferramenta de busca do servidor |
| `<P>_MAX_TOKENS` | Teto de tokens da resposta (padrão: 16000) |

Trocar de provedor é, portanto, uma edição no `.env`: o `.env.example` já traz o bloco do
Kimi pronto, comentado — ele expõe a mesma API da Anthropic, então o mesmo SDK atende
mudando só `KIMI_BASE_URL`.

---

## Como usar

### Análise por linha de comando

```powershell
python scripts/analisar.py                  # análise completa no terminal
python scripts/analisar.py --sem-ia         # somente cálculos, sem chamar a API
python scripts/analisar.py --telegram       # envia o relatório ao Telegram
python scripts/analisar.py --json           # saída bruta em JSON
python scripts/analisar.py --enviar-ultima  # reenvia ao Telegram a última análise
python scripts/analisar.py --testar-telegram
python scripts/analisar.py --help
```

### Interface web

```powershell
npm start
```

O navegador abre em `http://127.0.0.1:8765` e pede o usuário e a senha criados com
`node scripts/criarLogin.js` (veja a seção Instalação) antes de mostrar qualquer coisa.

Pela interface você cadastra posições, edita e exclui ativos, dispara a análise (que executa
o script Python por baixo) e vê o resultado na tela.

```powershell
npm start -- --porta 9000        # outra porta
npm start -- --sem-navegador     # não abre o navegador
```

### Docker

Imagem publicada em `ghcr.io/gadotti/analisador-financas`, a cada release marcada com tag
`v*.*.*` (veja `.github/workflows/release.yml`).

```powershell
copy .env.example .env
# edite o .env com o que for usar (IA, Telegram) — veja a seção Instalação
docker compose up -d
docker compose exec analisador-financas node scripts/criarLogin.js
```

O login é criado **depois** de o container estar de pé, rodando o script de dentro dele —
funciona porque `data/` (onde `criarLogin.js` grava) é um volume normal, gravável pelo
container, diferente do `.env` (montado somente leitura logo abaixo). Sem usuário nenhum
cadastrado o container sobe do mesmo jeito, só a tela de login fica inacessível até rodar
o comando acima.

O `docker-compose.yml` monta o `.env` da pasta atual em `/app/.env`, somente leitura
(precisa ser o arquivo de verdade — `ORIGEM_CHAVE=arquivo` lê a chave só dali), e persiste
`data/` (carteira, histórico e `usuarios.json`) num volume nomeado. A porta `8765` é
publicada em todas as interfaces, acessível por qualquer dispositivo da rede; para
restringir ao próprio host, troque o mapeamento no compose para `"127.0.0.1:8765:8765"`.

### Testes

```powershell
npm test           # Jest — aplicação Node (servidor, carteira, ponte com o script)
npm run coverage   # Jest com relatório de cobertura
npm run test:python
python -m pytest   # pytest — motor de análise (cálculos, IA, Telegram, CLI)
```

Nenhuma das duas suítes faz chamada de rede: cotações, Banco Central, Telegram e a API de
IA são todos substituídos por dublês. As duas isolam a configuração de IA num `.env`
temporário (via `IA_ENV_FILE`), para nunca ler o `.env` real do projeto.

---

## Cadastro de posições

**FIIs e ações** — ticker, quantidade e preço médio (data da compra é opcional).
A cotação atual é buscada automaticamente.

**CDBs, LCIs e LCAs** — banco emissor, valor aplicado, indexador, taxa, data de aplicação,
data de vencimento e a forma de pagamento dos juros.

| Indexador | O que informar na taxa | Exemplo |
|---|---|---|
| `CDI` | Percentual do CDI | `110` = 110% do CDI |
| `PRE` | Taxa prefixada ao ano | `12.5` = 12,5% a.a. |
| `IPCA` | Spread real sobre o IPCA | `6.5` = IPCA + 6,5% a.a. |

| Pagamento dos juros | Como o título se comporta |
|---|---|
| `No vencimento` (padrão) | O rendimento capitaliza e sai tudo no resgate |
| `Mensal` | Todo aniversário da aplicação paga os juros do mês e o principal segue intacto |
| `Semestral` (LCI, LCA) | O mesmo, a cada seis meses |

Num título de juros periódicos, o valor da posição é só o que continua aplicado — o
principal mais o rendimento do período em curso. Os cupons já sacados aparecem à parte,
líquidos de IR, na linha da posição e no relatório.

**LCI e LCA são isentas de IR** para a pessoa física: a taxa contratada nelas já é líquida,
e o sistema marca a posição como isenta em vez de descontar a tabela regressiva. É o que
torna 95% do CDI numa LCI melhor que 105% num CDB de mesmo prazo — a tela **Equivalência**
faz essa conversão para você antes de aplicar. Como têm carência legal, o cadastro não
oferece a elas a marcação de liquidez diária.

---

## O que o sistema calcula

**Sem IA, de forma determinística:**

- Valor atual, resultado acumulado e variação do dia de cada posição
- Marcação a mercado da renda fixa bancária em dias úteis (base 252) com o CDI vigente,
  incluindo o IR regressivo — ou a isenção da LCI e da LCA — para estimar o valor líquido
- Cronograma de cupons dos títulos de juros periódicos: quanto já foi recebido líquido,
  quantos pagamentos ocorreram e a data do próximo (sempre em dia útil)
- Alocação por classe e peso de cada ativo na carteira
- Alertas de vencimento de renda fixa, exposição por banco acima do teto do FGC (que soma
  o CDB, a LCI e a LCA do mesmo emissor, porque o teto é por CPF/instituição),
  concentração excessiva em um ativo e prejuízo relevante em renda variável

**Com IA (opcional):** busca notícias e dados recentes de cada ativo e do cenário macro,
e devolve fatos relevantes, pontos de observação e uma leitura do contexto de mercado —
sempre ancorada nos números que o sistema já calculou.

### Fontes de dados

| Dado | Fonte |
|---|---|
| Cotações da B3 | Yahoo Finance (primária), brapi.dev (alternativa) |
| CDI, Selic, IPCA | Banco Central — séries SGS 4389, 432 e 433 |
| Ibovespa | Yahoo Finance |
| Notícias e contexto | O provedor de IA configurado, com busca web |

Cotações ficam em cache por 15 minutos e indicadores por 12 horas, em `data/cache.json`.

---

## Estrutura

```
analise/                 MOTOR DE ANÁLISE (Python)
  portfolio.py           leitura da carteira
  market.py              cotações e indicadores macro, com cache
  fixed_income.py        marcação a mercado da renda fixa, dias úteis e IR
  analysis.py            consolidação da carteira e alertas (sem IA)
  fundamentals.py        métricas agregadas a partir das fichas da IA
  config_ia.py           provedor, modelo, esforço e chave, lidos do .env
  ai_insights.py         análise qualitativa via IA + busca web
  notifier.py            envio ao Telegram
  report.py              formatação para terminal e Telegram
  runner.py              orquestração e persistência
scripts/analisar.py      script isolado: terminal, agendador e interface

src/                     APLICAÇÃO WEB (Node.js)
  config/paths.js        caminhos do projeto
  core/portfolio.js      cadastro e validação das posições
  core/storage.js        leitura da última análise e do histórico
  server/app.js          servidor HTTP e rotas da API
  server/analiseExterna.js  ponte que dispara o script Python
  server/ambiente.js     checagem de IA e Telegram configurados
  config/configIa.js     leitura do provedor de IA declarado no .env
  server/index.js        inicialização (porta, navegador, sinais)
  util/                  datas e leitura do .env
web/                     interface (HTML, CSS e JavaScript sem dependências)

data/
  portfolio.json         sua carteira            (escrita pelo Node)
  last_analysis.json     última análise          (escrita pelo Python)
  history/               uma análise por dia     (escrita pelo Python)
  cache.json             cache de cotações       (escrita pelo Python)

test/                    testes da aplicação Node (Jest)
tests_analise/           testes do motor de análise (pytest)
```

O servidor usa apenas os módulos internos do Node: não há Express nem qualquer framework
web, e o Node não tem dependências de produção. Todas as bibliotecas externas do projeto
(`requests`, `anthropic`, `python-dotenv`) são do lado Python.

### Por que a análise fica isolada em um script

`scripts/analisar.py` é o **único ponto do sistema que fala com a API da Anthropic e com o
Telegram**. Ele roda de duas formas, sempre com o mesmo resultado:

1. Direto no terminal;
2. Como processo filho do servidor web, que lê o JSON do stdout.

Assim a interface fica livre de credenciais e de chamadas caras, a análise agendada e a
disparada pelo botão são exatamente a mesma coisa, e o script continua funcionando
sozinho mesmo que a interface não esteja aberta.

### Quem escreve o quê

Para que não existam duas regras para o mesmo arquivo, cada metade tem sua responsabilidade:

- **O Node escreve `portfolio.json`** (cadastro, validação, migração de formato) e apenas
  lê os resultados.
- **O Python lê `portfolio.json`** e escreve `last_analysis.json`, `history/` e `cache.json`.

---

## API local

O servidor expõe uma API própria, útil para integrar com outras ferramentas:

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/carteira` | Carteira completa |
| `POST` | `/api/posicoes` | Adiciona uma posição |
| `PUT` | `/api/posicoes/{id}` | Atualiza uma posição |
| `DELETE` | `/api/posicoes/{id}` | Remove uma posição |
| `POST` | `/api/config` | Salva perfil e limites de alerta |
| `POST` | `/api/analise?ia=1` | Executa o script Python (`ia=0` pula a IA) |
| `GET` | `/api/analise` | Última análise executada |
| `GET` | `/api/historico?limite=60` | Série histórica do valor da carteira |
| `POST` | `/api/telegram` | Envia a última análise ao Telegram |
| `POST` | `/api/telegram/testar` | Testa a conexão com o bot |
| `GET` | `/api/status` | Disponibilidade de IA e Telegram |

---

## Limitações conhecidas

- **Valores de renda fixa bancária são estimativas.** O cálculo projeta o CDI de hoje sobre
  todo o período decorrido e não considera carência, IOF nos primeiros 30 dias nem eventuais
  taxas. O extrato do banco é sempre a fonte oficial.
- **IPCA+ usa o índice divulgado**, que tem defasagem de algumas semanas em relação ao mês
  corrente. Num CDB IPCA+ de juros mensais, a correção acumulada é repartida entre os
  cupons na proporção dos dias úteis de cada um — uma aproximação, já que o índice não é
  linear no tempo.
- **O histórico começa hoje.** A série em `data/history/` é construída a partir das análises
  executadas — não há reconstrução retroativa.
- A análise por IA depende de busca web e pode não encontrar notícias sobre ativos de baixa
  liquidez.

---

## Aviso

As análises têm finalidade informativa e **não constituem recomendação de investimento**.
Consulte um profissional certificado antes de tomar decisões financeiras.

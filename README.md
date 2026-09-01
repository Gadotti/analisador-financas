# Portfolio Analyzer

Sistema local de acompanhamento e análise de carteira de investimentos — **FIIs, ações e CDBs**.
Cotações reais da B3, marcação a mercado de renda fixa, alertas automáticos e uma leitura
diária de mercado gerada por IA com busca web.

Tudo roda na sua máquina: os dados ficam em arquivos JSON locais e o servidor da interface
escuta apenas em `127.0.0.1`.

O projeto tem duas metades, cada uma na linguagem que lhe cai melhor:

| Parte | Linguagem | Papel |
|---|---|---|
| **Análise** (`analise/` + `scripts/analisar.py`) | Python | Cotações, marcação a mercado, alertas, IA e Telegram |
| **Aplicação** (`src/` + `web/`) | Node.js | Cadastro da carteira, interface web e API local |

A interface **dispara o script Python** quando você aperta o botão; o mesmo script roda
sozinho pelo Agendador de Tarefas ou pelo terminal.

---

## Instalação

Requer **Python 3.10+** e **Node.js 20.11+**.

```powershell
cd e:\Eduardo\Sistemas\analisador-financas
pip install -r requirements.txt
npm install
copy .env.example .env
```

Edite o `.env` conforme o que pretende usar. **Nada nele é obrigatório** — sem chave de API
o sistema continua calculando cotações, rentabilidade, alocação e alertas normalmente; só a
análise de mercado por IA fica indisponível.

| Variável | Para quê |
|---|---|
| `ANTHROPIC_API_KEY` | Análise de mercado por IA ([console.anthropic.com](https://console.anthropic.com/settings/keys)) |
| `ANTHROPIC_MODEL` / `ANTHROPIC_EFFORT` | Modelo e profundidade da análise (padrão: `claude-opus-5` / `medium`) |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Envio do relatório ao Telegram |
| `BRAPI_TOKEN` | Fonte alternativa de cotações |
| `PYTHON_BIN` | Interpretador Python que a interface deve chamar (útil com venv) |

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

Ou dê duplo clique em **`analisar.bat`**.

### Agendamento diário

```powershell
.\agendar_tarefa.ps1                              # seg-sex às 09:00
.\agendar_tarefa.ps1 -Horario "18:30" -ComTelegram
.\agendar_tarefa.ps1 -Remover
```

Registra a tarefa no Agendador de Tarefas do Windows, no contexto do seu usuário
(não exige administrador). A saída de cada execução é gravada em `analise.log`.

Para testar imediatamente: `Start-ScheduledTask -TaskName PortfolioAnalyzer`

### Interface web

```powershell
npm start
```

Ou dê duplo clique em **`iniciar_interface.bat`**. O navegador abre em `http://127.0.0.1:8765`.

Pela interface você cadastra posições, edita e exclui ativos, dispara a análise (que executa
o script Python por baixo) e vê o resultado na tela.

```powershell
npm start -- --porta 9000        # outra porta
npm start -- --sem-navegador     # não abre o navegador
```

### Testes

```powershell
npm test           # Jest — aplicação Node (servidor, carteira, ponte com o script)
npm run coverage   # Jest com relatório de cobertura
npm run test:python
python -m pytest   # pytest — motor de análise (cálculos, IA, Telegram, CLI)
```

Nenhuma das duas suítes faz chamada de rede: cotações, Banco Central, Telegram e a API da
Anthropic são todos substituídos por dublês.

---

## Cadastro de posições

**FIIs e ações** — ticker, quantidade e preço médio (data da compra é opcional).
A cotação atual é buscada automaticamente.

**CDBs** — banco emissor, valor aplicado, indexador, taxa, data de aplicação e data de
vencimento.

| Indexador | O que informar na taxa | Exemplo |
|---|---|---|
| `CDI` | Percentual do CDI | `110` = 110% do CDI |
| `PRE` | Taxa prefixada ao ano | `12.5` = 12,5% a.a. |
| `IPCA` | Spread real sobre o IPCA | `6.5` = IPCA + 6,5% a.a. |

---

## O que o sistema calcula

**Sem IA, de forma determinística:**

- Valor atual, resultado acumulado e variação do dia de cada posição
- Marcação a mercado de CDBs em dias úteis (base 252) com o CDI vigente, incluindo o
  IR regressivo para estimar o valor líquido
- Alocação por classe e peso de cada ativo na carteira
- Alertas de vencimento de CDB, exposição por banco acima do teto do FGC,
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
| Notícias e contexto | Claude com busca web |

Cotações ficam em cache por 15 minutos e indicadores por 12 horas, em `data/cache.json`.

---

## Estrutura

```
analise/                 MOTOR DE ANÁLISE (Python)
  portfolio.py           leitura da carteira
  market.py              cotações e indicadores macro, com cache
  fixed_income.py        marcação a mercado de CDBs, dias úteis e IR
  analysis.py            consolidação da carteira e alertas (sem IA)
  fundamentals.py        métricas agregadas a partir das fichas da IA
  ai_insights.py         análise qualitativa via Claude + busca web
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
agendar_tarefa.ps1       registra a tarefa no Agendador do Windows
```

O servidor usa apenas os módulos internos do Node: não há Express nem qualquer framework
web, e o Node não tem dependências de produção. Todas as bibliotecas externas do projeto
(`requests`, `anthropic`, `python-dotenv`) são do lado Python.

### Por que a análise fica isolada em um script

`scripts/analisar.py` é o **único ponto do sistema que fala com a API da Anthropic e com o
Telegram**. Ele roda de três formas, sempre com o mesmo resultado:

1. Direto no terminal;
2. Pelo Agendador de Tarefas do Windows;
3. Como processo filho do servidor web, que lê o JSON do stdout.

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

- **Valores de CDB são estimativas.** O cálculo projeta o CDI de hoje sobre todo o período
  decorrido e não considera carência, IOF nos primeiros 30 dias nem eventuais taxas. O
  extrato do banco é sempre a fonte oficial.
- **IPCA+ usa o índice divulgado**, que tem defasagem de algumas semanas em relação ao mês
  corrente.
- **O histórico começa hoje.** A série em `data/history/` é construída a partir das análises
  executadas — não há reconstrução retroativa.
- A análise por IA depende de busca web e pode não encontrar notícias sobre ativos de baixa
  liquidez.

---

## Aviso

As análises têm finalidade informativa e **não constituem recomendação de investimento**.
Consulte um profissional certificado antes de tomar decisões financeiras.

# Portfolio Analyzer

Sistema local de acompanhamento e análise de carteira de investimentos — **FIIs, ações e CDBs**.
Cotações reais da B3, marcação a mercado de renda fixa, alertas automáticos e uma leitura
diária de mercado gerada por IA com busca web.

Tudo roda na sua máquina: os dados ficam em arquivos JSON locais e o servidor da interface
escuta apenas em `127.0.0.1`.

---

## Instalação

```powershell
cd e:\Eduardo\Sistemas\fii-analyzer
pip install -r requirements.txt
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

---

## Como usar

### Interface web

```powershell
python server.py
```

Ou dê duplo clique em **`iniciar_interface.bat`**. O navegador abre em `http://127.0.0.1:8765`.

Pela interface você cadastra posições, edita e exclui ativos, dispara a análise e vê o
resultado na tela.

### Linha de comando

```powershell
python run_analysis.py               # análise completa no terminal
python run_analysis.py --sem-ia      # somente cálculos, sem chamar a API
python run_analysis.py --telegram    # envia o relatório ao Telegram
python run_analysis.py --json        # saída bruta em JSON
python run_analysis.py --testar-telegram
```

### Agendamento diário

```powershell
.\agendar_tarefa.ps1                              # seg-sex às 09:00
.\agendar_tarefa.ps1 -Horario "18:30" -ComTelegram
.\agendar_tarefa.ps1 -Remover
```

Registra a tarefa no Agendador de Tarefas do Windows, no contexto do seu usuário
(não exige administrador). A saída de cada execução é gravada em `analise.log`.

Para testar imediatamente: `Start-ScheduledTask -TaskName PortfolioAnalyzer`

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
core/
  portfolio.py      persistência e validação da carteira (JSON)
  market.py         cotações e indicadores macro, com cache
  fixed_income.py   marcação a mercado de CDBs, dias úteis e IR
  analysis.py       consolidação da carteira e alertas (sem IA)
  ai_insights.py    análise qualitativa via Claude + busca web
  report.py         formatação para terminal e Telegram
  notifier.py       envio ao Telegram
  runner.py         orquestração e persistência do histórico
data/
  portfolio.json    sua carteira
  last_analysis.json  última análise executada
  history/          uma análise por dia, para acompanhar a evolução
web/                interface (HTML, CSS e JavaScript sem dependências)
server.py           servidor local da interface + API
run_analysis.py     análise por linha de comando (usada pelo agendador)
agendar_tarefa.ps1  registra a tarefa no Agendador do Windows
legado/             versão anterior, somente FIIs — pode ser apagada
```

O `server.py` usa apenas a biblioteca padrão do Python: não há Flask nem qualquer framework
web para instalar.

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
| `POST` | `/api/analise?ia=1` | Executa a análise (`ia=0` pula a IA) |
| `GET` | `/api/analise` | Última análise executada |
| `GET` | `/api/historico?limite=60` | Série histórica do valor da carteira |
| `POST` | `/api/telegram` | Envia a última análise ao Telegram |
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

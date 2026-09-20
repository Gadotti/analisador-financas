# Auto-update — análise e próximas fases

Este documento continua a análise original sobre um sistema de auto-atualização
(detecção, download e aplicação de novas versões). A Fase 1 já foi implementada; as
fases seguintes ficam descritas aqui como plano, sem código, para retomar quando fizer
sentido.

## Fase 1 — Detecção e aviso (concluída)

Implementada em `src/server/atualizacao.js`, `GET /api/atualizacao` e na barra de aviso
da interface (`web/js/atualizacao.js`).

- Compara a `VERSAO` local com a última release do GitHub
  (`api.github.com/repos/Gadotti/analisador-financas/releases/latest`) — a mesma tag que
  também publica a imagem GHCR, então uma consulta só cobre host e container.
- Cache em memória de 6h no servidor; a checagem no front dispara a cada carregamento da
  página (`DOMContentLoaded`), não em intervalo enquanto a aba fica aberta.
- Falha de rede nunca aparece como erro para o usuário: vira `disponivel: false`.
- Só aviso — nenhuma ação de download ou aplicação.

## Fase 2 — Baixar o artefato da release para uma pasta específica

Diferente do que a análise original propunha, a Fase 2 **não aplica nada**: o único
trabalho é baixar o artefato da release e gravá-lo numa pasta de staging, deixando a
aplicação de fato (extrair, trocar arquivo, reiniciar processo, recriar container) para o
sidecar da Fase 3.

- **Onde**: uma pasta de staging dedicada, fora de `data/` (que é dado do usuário — ver
  a tabela "Quem escreve cada arquivo de dados" no `CLAUDE.md`) e fora do código-fonte.
  Um candidato natural é `_atualizacoes/` na raiz, ao lado de `_deploys/` (usado por
  `release.py` para o mesmo tipo de artefato, só que no momento do build em vez do
  runtime) — precisa entrar no `.gitignore`. A decisão final de caminho fica para quando
  a fase for implementada.
- **O que baixar**: o asset `.zip` da release do GitHub (o mesmo que `release.py` gera e
  o workflow publica). Isso vale para o cenário **host** — é o artefato que existe para
  baixar. Para o cenário **container** não há um arquivo equivalente: a atualização ali é
  a imagem Docker, que só se obtém com `docker pull`, uma operação que exige acesso ao
  Docker (daemon), não uma consulta HTTP simples. Portanto, em container, a Fase 2 se
  limita a expor "há uma versão nova, tag vX.Y.Z" — o próprio download/pull da imagem é
  trabalho do sidecar (Fase 3), que é quem terá a credencial/acesso para isso.
- **Integridade**: antes de gravar o zip como "pronto para aplicar", validar um checksum
  publicado na release. Hoje o `release.yml` não publica nenhum — precisa acrescentar um
  passo que gere e suba um `checksums.txt` (SHA-256) junto com o zip.
- **O que essa fase explicitamente não faz**: não extrai o zip sobre a instalação, não
  toca em nenhum arquivo de código em uso, não reinicia nada. O botão da interface nesta
  fase seria algo como "Baixar atualização" (preparar), separado de "Aplicar e
  reiniciar" (Fase 3).

## Fase 3 — Aplicar e reiniciar, via um sidecar dedicado

A aplicação principal nunca aplica a própria atualização nem se reinicia sozinha — quem
faz isso é uma **aplicação sidecar nova**, ainda a ser desenvolvida, rodando em paralelo
como processo (host) ou container (Docker) separado. É esse componente que resolve, de
uma vez, os dois problemas que a análise original tratava como fases distintas por
ambiente:

- **Host**: extrai o zip já baixado pela Fase 2 sobre o diretório de instalação,
  preservando `data/`, `.env` e `node_modules` (mesma exclusão que `release.py` já aplica
  ao gerar o zip), roda `npm ci --omit=dev` se o `package-lock.json` mudou, e reinicia o
  processo da aplicação principal.
- **Container**: puxa a nova tag da imagem (`docker pull`) e recria o container da
  aplicação principal — algo equivalente a `docker compose pull && docker compose up -d`,
  só que disparado programaticamete pelo sidecar.

### Por que um processo separado

Um processo não consegue substituir os próprios arquivos em disco e reiniciar a si mesmo
de forma confiável (era a limitação que a Fase 2 original, dentro do mesmo processo Node,
não resolvia — particularmente frágil no Windows, com arquivos abertos pelo próprio
`node.exe`). Um container também não consegue recriar a si mesmo de dentro dele mesmo. Um
sidecar independente resolve os dois casos com a mesma peça: ele continua rodando enquanto
a aplicação principal é substituída ou reiniciada por baixo dele.

### Fluxo de autorização

1. O usuário autenticado clica em "Aplicar atualização" na interface da aplicação
   principal (o mesmo gate de sessão que já protege todo `/api/*` continua valendo aqui).
2. A aplicação principal repassa esse pedido ao sidecar por um canal só acessível
   localmente — não exposto fora do host/container (bind em `127.0.0.1`, ou socket
   Unix/named pipe, no mesmo espírito de "servidor ouve em 127.0.0.1 por padrão" que já
   rege este projeto). Um HTTP interno simples, sem framework, seguiria o padrão que o
   projeto já usa para o script Python (`spawn` + leitura de stdout) — mas aqui é entre
   dois processos de longa duração, não um script que termina.
3. O sidecar executa a aplicação (extrai/pull + reinicia/recria) e devolve o resultado.
   Como a aplicação principal pode estar fora do ar durante a troca, o resultado da
   última tentativa precisa ficar disponível para a interface consultar depois que ela
   voltar (um arquivo de status simples, escrito pelo sidecar, resolveria isso).

### Superfície de segurança — isolar o risco no sidecar, não na aplicação principal

O ponto mais sensível de toda a proposta (mencionado na análise original) é o acesso ao
socket do Docker (`/var/run/docker.sock`), necessário para recriar o container em
ambiente Docker — equivalente, na prática, a acesso root sobre o host. A decisão desta
revisão é que **só o sidecar** tem esse acesso, nunca a aplicação principal: isso
concentra o componente de maior risco numa peça pequena, dedicada e auditável, em vez de
espalhar esse privilégio pela aplicação que também lida com os dados financeiros do
usuário. Ainda assim:

- O sidecar deve ser um serviço **opcional** no `docker-compose.yml` — quem não quiser
  auto-update em container simplesmente não o inclui.
- No host, o equivalente ao risco do socket do Docker é o sidecar ter permissão de
  escrita sobre o diretório de instalação e permissão para reiniciar o processo da
  aplicação — também deve ser algo que o usuário habilita explicitamente, não o padrão.
- O checksum da Fase 2 é o que impede o sidecar de aplicar um artefato corrompido ou
  adulterado — ele é quem de fato lê o zip do disco e o extrai sobre a instalação.

### Em aberto (decisões para quando esta fase for retomada)

- Linguagem/runtime do sidecar (Node, para reaproveitar módulos já existentes, ou algo
  mais simples e independente do resto da aplicação).
- Canal de comunicação exato entre aplicação principal e sidecar (HTTP local vs. arquivo
  de sinalização em disco).
- Formato do arquivo/local de status que o sidecar deixa para a aplicação principal ler
  depois de voltar ao ar.
- Onde fica a pasta de staging da Fase 2 e sua política de limpeza (versões antigas
  baixadas e não aplicadas).

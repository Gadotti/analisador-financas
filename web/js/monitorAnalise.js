/**
 * Vigia a análise em disco e decide quando mostrá-la.
 *
 * O script Python também roda fora do servidor (tarefa agendada, terminal), então
 * a interface só descobre uma análise nova perguntando. A pergunta é barata —
 * `GET /api/analise/versao` devolve só a impressão digital do arquivo — e a
 * análise inteira só é buscada quando essa versão muda.
 *
 * Mostrar é outra decisão: com a tela livre, aplica em silêncio; com o usuário no
 * meio de algo (`ocupado`), apenas avisa, e ele aplica quando quiser. Nada aqui
 * toca o DOM — tudo entra por parâmetro, o que permite testar sem navegador.
 */

const INTERVALO_PADRAO_MS = 60_000;

/**
 * @param {object} dependencias
 * @param {() => Promise<{versao: string|null, atualizada_em: string|null}>} dependencias.consultarVersao
 * @param {() => Promise<void>} dependencias.aplicar Busca a análise e redesenha a tela.
 * @param {() => boolean} dependencias.ocupado O usuário está no meio de uma ação?
 * @param {(aviso: object|null) => void} dependencias.avisar Mostra (ou, com null, esconde) o aviso.
 * @param {(info: object) => void} [dependencias.aoAplicarSozinho] Chamado após uma aplicação silenciosa.
 */
export function criarMonitorAnalise({ consultarVersao, aplicar, ocupado, avisar, aoAplicarSozinho }) {
  // `undefined`: ainda não sabemos o que está na tela. `null`: sabemos que não há análise.
  let naTela;
  let pendente = null;
  let consultando = false;

  /**
   * Anota a versão que a tela já reflete e desfaz qualquer aviso. Uma falha na
   * consulta não sobe: quem chama acabou de carregar a análise com sucesso, e o
   * vigia adota a primeira versão que conseguir ler.
   */
  async function registrar() {
    try {
      const { versao } = await consultarVersao();
      naTela = versao;
      pendente = null;
      avisar(null);
    } catch {
      // sem a versão agora; o próximo ciclo de `verificar` a anota.
    }
  }

  async function aplicarVersao(info) {
    await aplicar();
    naTela = info.versao;
    pendente = null;
    avisar(null);
  }

  /** Um ciclo de vigia: consulta e, se houver novidade, aplica ou avisa. */
  async function verificar() {
    if (consultando) return;
    consultando = true;
    try {
      const info = await consultarVersao();
      if (naTela === undefined) {
        naTela = info.versao;
        return;
      }
      if (info.versao === null || info.versao === naTela) return;
      if (ocupado()) {
        pendente = info;
        avisar(info);
        return;
      }
      await aplicarVersao(info);
      aoAplicarSozinho?.(info);
    } catch {
      // rede fora ou servidor reiniciando: o próximo ciclo tenta de novo.
    } finally {
      consultando = false;
    }
  }

  /** O usuário pediu a atualização que estava pendente. */
  async function aplicarPendente() {
    const alvo = pendente ?? (await consultarVersao());
    if (alvo.versao === null) return;
    await aplicarVersao(alvo);
  }

  return { registrar, verificar, aplicarPendente, temPendente: () => pendente !== null };
}

/**
 * Liga o vigia ao relógio e à aba: consulta a cada intervalo enquanto a aba está
 * à vista e, ao voltar a ela, na hora — é quando o usuário mais provavelmente
 * olha para os números. Devolve a função que desliga tudo.
 */
export function iniciarVigia(
  monitor,
  { intervaloMs = INTERVALO_PADRAO_MS, documento = document, janela = window } = {}
) {
  const aoVoltar = () => {
    if (!documento.hidden) monitor.verificar();
  };
  const relogio = setInterval(() => {
    if (!documento.hidden) monitor.verificar();
  }, intervaloMs);

  documento.addEventListener("visibilitychange", aoVoltar);
  janela.addEventListener("focus", aoVoltar);

  return () => {
    clearInterval(relogio);
    documento.removeEventListener("visibilitychange", aoVoltar);
    janela.removeEventListener("focus", aoVoltar);
  };
}

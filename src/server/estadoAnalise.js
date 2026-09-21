/**
 * Estado em memória da análise disparada pelo servidor.
 *
 * Não é persistido — reinicia a cada `npm start` — e existe só para a
 * interface saber, enquanto o script Python roda, se a análise está mesmo em
 * andamento, há quanto tempo e em que fase (via `aoRegistrar` de
 * `analiseExterna.rodarScript`, que repassa o stderr do script linha a
 * linha). `execucoes.json` só recebe uma linha quando o processo termina —
 * uma queda no meio (timeout, kill) não deixa rastro lá, e é esse buraco que
 * `ultimoErro` cobre.
 */

export function criarEstadoAnalise() {
  return {
    emAndamento: false,
    comIa: null,
    iniciadaEm: null,
    fase: null,
    ultimoErro: null,
    ultimoErroEm: null,
  };
}

/** Marca o início de uma execução, limpando o erro da tentativa anterior. */
export function iniciar(estado, { comIa }) {
  estado.emAndamento = true;
  estado.comIa = comIa;
  estado.iniciadaEm = new Date().toISOString();
  estado.fase = null;
  estado.ultimoErro = null;
  estado.ultimoErroEm = null;
}

/** Chamado a cada linha de progresso que o script escreve no stderr. */
export function atualizarFase(estado, linha) {
  estado.fase = linha;
}

export function finalizarComSucesso(estado) {
  estado.emAndamento = false;
  estado.fase = null;
}

export function finalizarComErro(estado, mensagem) {
  estado.emAndamento = false;
  estado.fase = null;
  estado.ultimoErro = mensagem;
  estado.ultimoErroEm = new Date().toISOString();
}

/** Formato exposto por GET /api/analise/status — chaves snake_case, como o resto da API. */
export function paraApi(estado) {
  return {
    em_andamento: estado.emAndamento,
    com_ia: estado.comIa,
    iniciada_em: estado.iniciadaEm,
    fase: estado.fase,
    ultimo_erro: estado.ultimoErro,
    ultimo_erro_em: estado.ultimoErroEm,
  };
}

/**
 * Limite de tentativas de login por IP — só em memória, um processo só.
 *
 * Não é bloqueio de conta (não há conta, o login é único e só libera o
 * acesso à ferramenta): é o freio contra força bruta que um framework daria
 * de graça (era `express-rate-limit` no ShadowRadar). `agora` é injetável
 * para os testes não dependerem de esperar a janela passar de verdade.
 */

export const MAX_TENTATIVAS = 10;
export const JANELA_MS = 15 * 60 * 1000;

const tentativasPorIp = new Map();

function registroAtual(ip, agora) {
  const existente = tentativasPorIp.get(ip);
  if (existente && existente.expiraEm > agora) return existente;

  const novo = { contagem: 0, expiraEm: agora + JANELA_MS };
  tentativasPorIp.set(ip, novo);
  return novo;
}

/** true se o IP já esgotou as tentativas na janela atual. */
export function bloqueado(ip, agora = Date.now()) {
  const existente = tentativasPorIp.get(ip);
  return Boolean(existente && existente.expiraEm > agora && existente.contagem >= MAX_TENTATIVAS);
}

/** Conta mais uma tentativa malsucedida para o IP. */
export function registrarFalha(ip, agora = Date.now()) {
  registroAtual(ip, agora).contagem += 1;
}

/** Login bem-sucedido: zera o contador do IP. */
export function limpar(ip) {
  tentativasPorIp.delete(ip);
}

/** Descarta todo o estado — usado só entre suítes de teste. */
export function reiniciar() {
  tentativasPorIp.clear();
}

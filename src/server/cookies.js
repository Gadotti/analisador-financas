/** Cookie de sessão e leitura do cabeçalho Cookie — sem dependência externa. */

const NOME = "sessao";

/** Cabeçalho Cookie da requisição, como {nome: valor}. */
export function analisarCookies(req) {
  const cabecalho = req.headers.cookie;
  const cookies = {};
  if (!cabecalho) return cookies;

  for (const par of cabecalho.split(";")) {
    const igual = par.indexOf("=");
    if (igual === -1) continue;
    const nome = par.slice(0, igual).trim();
    if (nome) cookies[nome] = decodeURIComponent(par.slice(igual + 1).trim());
  }
  return cookies;
}

/** Token de sessão enviado pelo navegador, ou null se não houver cookie. */
export function tokenDaRequisicao(req) {
  return analisarCookies(req)[NOME] || null;
}

/** Cabeçalho Set-Cookie para uma sessão nova, válida por duracaoMs. */
export function cookieSessao(token, duracaoMs) {
  const maxAge = Math.floor(duracaoMs / 1000);
  return `${NOME}=${encodeURIComponent(token)}; HttpOnly; SameSite=Strict; Path=/; Max-Age=${maxAge}`;
}

/** Cabeçalho Set-Cookie que apaga a sessão (logout). */
export function cookieLogout() {
  return `${NOME}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0`;
}

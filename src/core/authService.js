/**
 * Hash de senha e token de sessão — só com o módulo crypto nativo do Node.
 *
 * Sem bcrypt nem jsonwebtoken (o projeto não tem dependências de produção):
 * scrypt faz o papel do bcrypt (custo de memória, resistente a força bruta em
 * GPU), e um HMAC-SHA256 sobre um payload JSON faz o de um JWT mínimo — só o
 * suficiente para um login único que apenas libera o acesso à ferramenta.
 */

import crypto from "node:crypto";

const TAMANHO_HASH = 64;
const TAMANHO_SAL = 16;

/** Validade da sessão: 30 dias, o mesmo período usado por padrão em apps locais. */
export const SESSAO_MS = 30 * 24 * 60 * 60 * 1000;

/** "sal:hash", ambos em hexadecimal — o formato gravado em AUTH_SENHA_HASH. */
export function gerarHashSenha(senha) {
  const sal = crypto.randomBytes(TAMANHO_SAL);
  const hash = crypto.scryptSync(senha, sal, TAMANHO_HASH);
  return `${sal.toString("hex")}:${hash.toString("hex")}`;
}

/**
 * Compara em tempo constante. Nunca lança: um hash malformado (arquivo
 * corrompido, campo vazio) só faz a senha ser considerada incorreta.
 */
export function conferirSenha(senha, hashArmazenado) {
  const [salHex, hashHex] = String(hashArmazenado || "").split(":");
  if (!salHex || !hashHex) return false;

  const sal = Buffer.from(salHex, "hex");
  const esperado = Buffer.from(hashHex, "hex");
  if (sal.length === 0 || esperado.length === 0) return false;

  const calculado = crypto.scryptSync(senha, sal, esperado.length);
  return crypto.timingSafeEqual(calculado, esperado);
}

const base64Url = (buffer) => buffer.toString("base64url");
const assinar = (payloadBase64, segredo) =>
  crypto.createHmac("sha256", segredo).update(payloadBase64).digest();

/** Token de sessão: validade + assinatura HMAC, sem nenhum estado guardado no servidor. */
export function criarToken(segredo, duracaoMs = SESSAO_MS, agora = Date.now()) {
  const payloadBase64 = base64Url(Buffer.from(JSON.stringify({ exp: agora + duracaoMs }), "utf8"));
  return `${payloadBase64}.${base64Url(assinar(payloadBase64, segredo))}`;
}

/** true só se a assinatura confere com o segredo e o token ainda não expirou. */
export function tokenValido(token, segredo, agora = Date.now()) {
  if (typeof token !== "string" || typeof segredo !== "string" || !segredo) return false;

  const separador = token.indexOf(".");
  if (separador === -1) return false;
  const payloadBase64 = token.slice(0, separador);
  const assinatura = token.slice(separador + 1);
  if (!payloadBase64 || !assinatura) return false;

  const esperada = assinar(payloadBase64, segredo);
  const recebida = Buffer.from(assinatura, "base64url");
  if (recebida.length !== esperada.length || !crypto.timingSafeEqual(recebida, esperada)) {
    return false;
  }

  try {
    const payload = JSON.parse(Buffer.from(payloadBase64, "base64url").toString("utf8"));
    return typeof payload.exp === "number" && payload.exp > agora;
  } catch {
    return false;
  }
}

/**
 * Credenciais de login e segredo de sessão, declaradas no .env.
 *
 * Mesma forma de configIa.js: leitura só do arquivo, nunca gravação — quem
 * grava é scripts/criarLogin.js. AUTH_ENV_FILE troca o caminho, exatamente
 * como IA_ENV_FILE isola a configuração de IA; é assim que os testes evitam
 * ler o .env real do usuário.
 *
 * Autenticação não é opcional como o provedor de IA: sem as três variáveis
 * definidas, o servidor recusa subir (veja src/server/index.js) e nenhuma
 * sessão é aceita.
 */

import path from "node:path";

import { lerArquivoEnv } from "../util/env.js";
import { BASE_DIR } from "./paths.js";

/** Login não configurado ou incompleto no .env. */
export class AutenticacaoError extends Error {
  constructor(mensagem) {
    super(mensagem);
    this.name = "AutenticacaoError";
  }
}

/** Arquivo .env em uso. AUTH_ENV_FILE redireciona (é assim que os testes isolam). */
export function arquivoEnvAuth() {
  return process.env.AUTH_ENV_FILE || path.join(BASE_DIR, ".env");
}

function exigir(doArquivo, nome) {
  const lido = (doArquivo[nome] || "").trim();
  if (!lido) {
    throw new AutenticacaoError(
      `${nome} não definida em ${arquivoEnvAuth()}. Rode "node scripts/criarLogin.js" para criar o login.`,
    );
  }
  return lido;
}

/**
 * Usuário, hash da senha e segredo de sessão.
 * Lança AutenticacaoError se qualquer um dos três não estiver definido.
 */
export function configuracaoAuth() {
  const doArquivo = lerArquivoEnv(arquivoEnvAuth());
  return {
    usuario: exigir(doArquivo, "AUTH_USUARIO"),
    senhaHash: exigir(doArquivo, "AUTH_SENHA_HASH"),
    segredoSessao: exigir(doArquivo, "AUTH_SESSAO_SEGREDO"),
  };
}

/**
 * Leitura e gravação das propriedades do .env expostas na tela de
 * Configurações — provedor de IA, Telegram e o token opcional da brapi.
 *
 * Segredos (chave de API, token do bot) nunca são devolvidos: só a presença é
 * informada (`*_definida`). Gravar um campo de segredo em branco mantém o
 * valor já salvo — é assim que a tela evita reexibir a credencial.
 */

import { lerArquivoEnv, salvarValoresEnv } from "../util/env.js";
import { arquivoEnvIa, ORIGENS, prefixoProvedor } from "./configIa.js";

export const PROVEDORES_CONHECIDOS = ["anthropic", "kimi"];

const CAMPOS_TEXTO = [
  "origem_chave",
  "variavel_chave",
  "model",
  "effort",
  "base_url",
  "fallback",
  "busca_web",
  "max_tokens",
];

const nomeVariavel = (prefixo, campo) => `${prefixo}${campo.toUpperCase()}`;

function lerBlocoProvedor(doArquivo, nome) {
  const prefixo = prefixoProvedor(nome);
  const bloco = {};
  for (const campo of CAMPOS_TEXTO) bloco[campo] = doArquivo[nomeVariavel(prefixo, campo)] || "";
  bloco.api_key_definida = Boolean((doArquivo[`${prefixo}API_KEY`] || "").trim());
  return bloco;
}

/** Estado atual do .env para a tela de Configurações, sem segredos. */
export function lerPainelEnv() {
  const doArquivo = lerArquivoEnv(arquivoEnvIa());
  const provedores = {};
  for (const nome of PROVEDORES_CONHECIDOS) provedores[nome] = lerBlocoProvedor(doArquivo, nome);

  return {
    ia_provedor: doArquivo.IA_PROVEDOR || "",
    origens_chave: ORIGENS,
    provedores,
    telegram: {
      chat_id: doArquivo.TELEGRAM_CHAT_ID || "",
      bot_token_definido: Boolean((doArquivo.TELEGRAM_BOT_TOKEN || "").trim()),
    },
    brapi_token_definido: Boolean((doArquivo.BRAPI_TOKEN || "").trim()),
  };
}

function coletarAlteracoesProvedor(alteracoes, nome, bloco) {
  const prefixo = prefixoProvedor(nome);
  for (const campo of CAMPOS_TEXTO) {
    if (typeof bloco[campo] === "string") alteracoes[nomeVariavel(prefixo, campo)] = bloco[campo].trim();
  }
  if (typeof bloco.api_key === "string" && bloco.api_key.trim()) {
    alteracoes[`${prefixo}API_KEY`] = bloco.api_key.trim();
  }
}

/**
 * Grava as alterações vindas da tela de Configurações. Lança
 * ConfiguracaoIaError (de configIa.js) se `ia_provedor` não virar um prefixo
 * válido — mesma regra usada para ler a configuração ativa.
 */
export function salvarPainelEnv(corpo) {
  const alteracoes = {};

  if (typeof corpo.ia_provedor === "string") {
    prefixoProvedor(corpo.ia_provedor || "anthropic");
    alteracoes.IA_PROVEDOR = corpo.ia_provedor.trim();
  }

  for (const nome of PROVEDORES_CONHECIDOS) {
    const bloco = corpo.provedores?.[nome];
    if (bloco) coletarAlteracoesProvedor(alteracoes, nome, bloco);
  }

  if (corpo.telegram) {
    if (typeof corpo.telegram.chat_id === "string") {
      alteracoes.TELEGRAM_CHAT_ID = corpo.telegram.chat_id.trim();
    }
    if (typeof corpo.telegram.bot_token === "string" && corpo.telegram.bot_token.trim()) {
      alteracoes.TELEGRAM_BOT_TOKEN = corpo.telegram.bot_token.trim();
    }
  }
  if (typeof corpo.brapi_token === "string" && corpo.brapi_token.trim()) {
    alteracoes.BRAPI_TOKEN = corpo.brapi_token.trim();
  }

  salvarValoresEnv(arquivoEnvIa(), alteracoes);
  for (const [chave, valor] of Object.entries(alteracoes)) process.env[chave] = valor;

  return lerPainelEnv();
}

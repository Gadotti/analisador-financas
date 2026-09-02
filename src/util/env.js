/**
 * Leitura do arquivo .env.
 *
 * Parser próprio, de propósito: são poucas linhas, tem um caminho de execução
 * só e não depende da versão do Node.
 *
 * Duas portas de entrada, com precedências opostas de propósito:
 * `carregarEnv()` popula process.env sem sobrescrever o que já veio do
 * ambiente; `lerArquivoEnv()` devolve o conteúdo do arquivo sem tocar em
 * process.env, para quem precisa do que **o arquivo** diz (veja config/configIa.js).
 */

import fs from "node:fs";
import path from "node:path";

import { BASE_DIR } from "../config/paths.js";

const LINHA = /^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/;

function semAspas(valor) {
  const texto = valor.trim();
  const aspas = texto.startsWith('"') && texto.endsWith('"');
  const apostrofos = texto.startsWith("'") && texto.endsWith("'");
  return (aspas || apostrofos) && texto.length >= 2 ? texto.slice(1, -1) : texto;
}

export function arquivoEnvPadrao() {
  return path.join(BASE_DIR, ".env");
}

/**
 * Pares chave=valor do arquivo, sem mexer em process.env.
 * @returns {Record<string, string>} objeto vazio se o arquivo não existir.
 */
export function lerArquivoEnv(arquivo = arquivoEnvPadrao()) {
  let conteudo;
  try {
    conteudo = fs.readFileSync(arquivo, "utf8");
  } catch {
    return {};
  }

  const valores = {};
  for (const linha of conteudo.split(/\r?\n/)) {
    const casa = LINHA.exec(linha);
    if (casa) valores[casa[1]] = semAspas(casa[2]);
  }
  return valores;
}

/**
 * Lê o arquivo e popula process.env. Variáveis já presentes no ambiente têm
 * precedência sobre o arquivo.
 * @returns {boolean} true se o arquivo existia e foi lido.
 */
export function carregarEnv(arquivo = arquivoEnvPadrao()) {
  if (!fs.existsSync(arquivo)) return false;

  for (const [chave, valor] of Object.entries(lerArquivoEnv(arquivo))) {
    if (process.env[chave] === undefined) process.env[chave] = valor;
  }
  return true;
}

/**
 * Carga do arquivo .env.
 *
 * Parser próprio, de propósito: são poucas linhas, tem um caminho de execução
 * só e não depende da versão do Node. Variáveis já presentes no ambiente têm
 * precedência sobre o arquivo.
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

/**
 * Lê o arquivo e popula process.env.
 * @returns {boolean} true se o arquivo existia e foi lido.
 */
export function carregarEnv(arquivo = path.join(BASE_DIR, ".env")) {
  if (!fs.existsSync(arquivo)) return false;

  for (const linha of fs.readFileSync(arquivo, "utf8").split(/\r?\n/)) {
    const casa = LINHA.exec(linha);
    if (!casa) continue;
    const [, chave, bruto] = casa;
    if (process.env[chave] === undefined) process.env[chave] = semAspas(bruto);
  }
  return true;
}

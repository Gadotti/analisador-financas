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

/**
 * `semAspas` só remove as aspas que envolvem o valor, sem interpretar escapes —
 * por isso a aspa escolhida aqui precisa ser a que não aparece dentro do
 * texto, para o par escrito e lido bater.
 */
function comAspasSeNecessario(valor) {
  const texto = String(valor ?? "");
  if (!/[\s#"']/.test(texto)) return texto;
  if (!texto.includes('"')) return `"${texto}"`;
  if (!texto.includes("'")) return `'${texto}'`;
  return texto;
}

/**
 * Grava pares chave=valor no arquivo, preservando as demais linhas (comentários
 * e variáveis não alteradas). Uma chave ausente é acrescentada ao final; o
 * arquivo é criado se não existir. Usado pela tela de Configurações — nunca
 * pelo cadastro da carteira, que mora só em `data/`.
 */
export function salvarValoresEnv(arquivo, alteracoes) {
  const pendentes = new Map(Object.entries(alteracoes));
  let linhas = [];
  try {
    linhas = fs.readFileSync(arquivo, "utf8").split(/\r?\n/);
  } catch {
    linhas = [];
  }

  const resultado = linhas.map((linha) => {
    const casa = LINHA.exec(linha);
    if (!casa || !pendentes.has(casa[1])) return linha;
    const valor = pendentes.get(casa[1]);
    pendentes.delete(casa[1]);
    return `${casa[1]}=${comAspasSeNecessario(valor)}`;
  });

  if (pendentes.size > 0) {
    if (resultado.length && resultado[resultado.length - 1].trim() !== "") resultado.push("");
    for (const [chave, valor] of pendentes) {
      resultado.push(`${chave}=${comAspasSeNecessario(valor)}`);
    }
  }

  fs.mkdirSync(path.dirname(arquivo), { recursive: true });
  fs.writeFileSync(arquivo, resultado.join("\n"), "utf8");
}

/**
 * Caminhos padrão do projeto.
 *
 * Todos são resolvidos a cada chamada (e não no carregamento do módulo) para
 * que os testes possam apontar PORTFOLIO_DATA_DIR para um diretório temporário.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const BASE_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

export const WEB_DIR = path.join(BASE_DIR, "web");
export const SCRIPTS_DIR = path.join(BASE_DIR, "scripts");
export const SCRIPT_ANALISE = path.join(SCRIPTS_DIR, "analisar.py");

export function dataDir() {
  return process.env.PORTFOLIO_DATA_DIR || path.join(BASE_DIR, "data");
}

export function historyDir() {
  return path.join(dataDir(), "history");
}

export function portfolioFile() {
  return path.join(dataDir(), "portfolio.json");
}

export function cacheFile() {
  return path.join(dataDir(), "cache.json");
}

export function lastAnalysisFile() {
  return path.join(dataDir(), "last_analysis.json");
}

/** Log de execuções, escrito pelo Python a cada rodada (uma linha por execução). */
export function execucoesFile() {
  return path.join(dataDir(), "execucoes.json");
}

/** Usuários do login e segredo de sessão — só o Node lê e escreve. */
export function usuariosFile() {
  return path.join(dataDir(), "usuarios.json");
}

/** Cria os diretórios de dados. Chamado antes de qualquer escrita. */
export function garantirDiretorios() {
  fs.mkdirSync(historyDir(), { recursive: true });
}

#!/usr/bin/env node
/**
 * Cria (ou troca) o login único da interface web.
 *
 * Uso:
 *   node scripts/criarLogin.js
 *
 * Pede usuário e senha no terminal e grava o hash da senha no .env — nunca a
 * senha em texto puro (veja src/core/authService.js). Na primeira vez também
 * gera o segredo de sessão (AUTH_SESSAO_SEGREDO); rodar de novo para trocar a
 * senha mantém o segredo já existente, para não derrubar sessões abertas por
 * um motivo que não é a troca da senha em si.
 */

import crypto from "node:crypto";
import readline from "node:readline";

import { arquivoEnvAuth } from "../src/config/authConfig.js";
import { gerarHashSenha } from "../src/core/authService.js";
import { lerArquivoEnv, salvarValoresEnv } from "../src/util/env.js";

const CODIGO_CTRL_C = 3;
const CODIGO_BACKSPACE = 8;
const CODIGO_DEL = 127;

function perguntar(rl, texto) {
  return new Promise((resolve) => rl.question(texto, resolve));
}

/** Lê uma linha do terminal sem ecoar os caracteres digitados. */
function perguntarSenha(texto) {
  return new Promise((resolve) => {
    process.stdout.write(texto);
    const stdin = process.stdin;
    const eraRaw = stdin.isRaw;
    stdin.setRawMode?.(true);
    stdin.resume();
    stdin.setEncoding("utf8");

    let senha = "";
    function limpar() {
      stdin.removeListener("data", aoDigitar);
      stdin.setRawMode?.(eraRaw);
      stdin.pause();
    }
    function aoDigitar(char) {
      const codigo = char.charCodeAt(0);

      if (codigo === CODIGO_CTRL_C) {
        limpar();
        process.stdout.write("\n");
        process.exit(130);
      }
      if (char === "\r" || char === "\n") {
        limpar();
        process.stdout.write("\n");
        resolve(senha);
        return;
      }
      if (codigo === CODIGO_BACKSPACE || codigo === CODIGO_DEL) {
        senha = senha.slice(0, -1);
        return;
      }
      senha += char;
    }
    stdin.on("data", aoDigitar);
  });
}

async function main() {
  const arquivo = arquivoEnvAuth();
  const doArquivo = lerArquivoEnv(arquivo);

  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  const usuario = (await perguntar(rl, "Usuário: ")).trim();
  rl.close();

  if (!usuario) {
    process.stderr.write("Usuário não pode ser vazio.\n");
    process.exitCode = 1;
    return;
  }

  const senha = await perguntarSenha("Senha: ");
  const confirmacao = await perguntarSenha("Confirme a senha: ");
  if (!senha) {
    process.stderr.write("Senha não pode ser vazia.\n");
    process.exitCode = 1;
    return;
  }
  if (senha !== confirmacao) {
    process.stderr.write("As senhas não conferem.\n");
    process.exitCode = 1;
    return;
  }

  const alteracoes = {
    AUTH_USUARIO: usuario,
    AUTH_SENHA_HASH: gerarHashSenha(senha),
  };
  if (!(doArquivo.AUTH_SESSAO_SEGREDO || "").trim()) {
    alteracoes.AUTH_SESSAO_SEGREDO = crypto.randomBytes(32).toString("hex");
  }

  salvarValoresEnv(arquivo, alteracoes);
  process.stdout.write(`\nLogin salvo em ${arquivo}. Rode "npm start" e entre com este usuário e senha.\n`);
}

main();

#!/usr/bin/env node
/**
 * Cria um usuário de login (ou troca a senha de um já existente).
 *
 * Uso:
 *   node scripts/criarLogin.js
 *
 * Também funciona de dentro do container Docker, porque data/ é um volume
 * gravável (diferente do .env, montado :ro no docker-compose.yml):
 *   docker compose exec analisador-financas node scripts/criarLogin.js
 *
 * Pede usuário e senha no terminal e grava o hash da senha em
 * data/usuarios.json — nunca a senha em texto puro (veja
 * src/core/authService.js). Aceita mais de um usuário: todos autenticam
 * contra os mesmos dados, sem segregação nenhuma — o login só existe para
 * liberar o acesso à ferramenta. Rodar de novo com um usuário já existente
 * troca só a senha dele.
 */

import readline from "node:readline";

import { usuariosFile } from "../src/config/paths.js";
import { criarOuAtualizarUsuario } from "../src/core/usuarios.js";

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

  const { criado } = criarOuAtualizarUsuario(usuario, senha);
  const acao = criado ? "Usuário criado" : "Senha atualizada";
  process.stdout.write(
    `\n${acao} em ${usuariosFile()}. Rode "npm start" e entre com este usuário e senha.\n`,
  );
}

main();

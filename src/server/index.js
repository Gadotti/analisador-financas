#!/usr/bin/env node
/**
 * Inicialização do servidor local da interface web.
 *
 * Uso:
 *   node src/server/index.js
 *   node src/server/index.js --porta 9000
 *   node src/server/index.js --sem-navegador
 *
 * Ouve em 127.0.0.1 por padrão; a variável de ambiente `HOST` muda o
 * endereço, para expor a interface na rede (é o que o `docker-compose.yml` usa).
 */

import { exec } from "node:child_process";
import process from "node:process";
import { pathToFileURL } from "node:url";

import { AutenticacaoError, configuracaoAuth } from "../core/usuarios.js";
import { carregarEnv } from "../util/env.js";
import * as ambiente from "./ambiente.js";
import { interpretadorPython } from "./analiseExterna.js";
import { criarServidor } from "./app.js";

export const PORTA_PADRAO = 8765;
export const HOST = process.env.HOST || "127.0.0.1";

export function parseArgs(argv) {
  const opcoes = { porta: PORTA_PADRAO, semNavegador: false };
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === "--porta") {
      // A porta 0 é válida: o sistema escolhe uma porta livre.
      const porta = Number.parseInt(argv[i + 1], 10);
      if (!Number.isInteger(porta) || porta < 0 || porta > 65535) {
        throw new Error(`Porta inválida: ${argv[i + 1]}`);
      }
      opcoes.porta = porta;
      i += 1;
    } else if (argv[i] === "--sem-navegador") {
      opcoes.semNavegador = true;
    } else {
      throw new Error(`Opção desconhecida: ${argv[i]}`);
    }
  }
  return opcoes;
}

/**
 * Monta o comando de abertura do navegador para a plataforma informada.
 * Separado de `abrirNavegador` para poder ser testado sem abrir nada.
 */
export function comandoNavegador(endereco, plataforma = process.platform) {
  if (plataforma === "win32") return `start "" "${endereco}"`;
  if (plataforma === "darwin") return `open "${endereco}"`;
  return `xdg-open "${endereco}"`;
}

/** Abre o navegador padrão do sistema no endereço informado. */
export function abrirNavegador(endereco, { executar = exec } = {}) {
  executar(comandoNavegador(endereco), () => {});
}

/** true se já existe pelo menos um usuário cadastrado em data/usuarios.json. */
function loginConfigurado() {
  try {
    configuracaoAuth();
    return true;
  } catch (erro) {
    if (erro instanceof AutenticacaoError) return false;
    throw erro;
  }
}

export function iniciar(argv = []) {
  carregarEnv();
  const { porta, semNavegador } = parseArgs(argv);
  const endereco = `http://${HOST}:${porta}`;

  // Sem usuário cadastrado o servidor sobe do mesmo jeito — cada requisição
  // não autenticada é tratada como tal (redireciona para /login, ou 401 na
  // API); só o próprio login falha, até alguém rodar scripts/criarLogin.js.
  const servidor = criarServidor();

  servidor.listen(porta, HOST, () => {
    const { ok, motivo } = ambiente.statusIa();
    process.stdout.write(`\n  Analisador de Finanças — ${endereco}\n`);
    process.stdout.write(
      `  Login: ${
        loginConfigurado() ? "configurado" : 'não configurado — rode "node scripts/criarLogin.js"'
      }\n`,
    );
    process.stdout.write(
      `  Análise por IA: ${
        ok
          ? `disponível (${ambiente.provedorIa()} · ${ambiente.modeloIa()})`
          : `indisponível — ${motivo}`
      }\n`,
    );
    process.stdout.write(
      `  Telegram: ${ambiente.telegramConfigurado() ? "configurado" : "não configurado"}\n`,
    );
    process.stdout.write(`  Análise: ${interpretadorPython()} scripts/analisar.py\n`);
    process.stdout.write("  Ctrl+C para encerrar.\n\n");

    if (!semNavegador) setTimeout(() => abrirNavegador(endereco), 800).unref();
  });

  servidor.on("error", (erro) => {
    if (erro.code === "EADDRINUSE") {
      process.stderr.write(
        `\n  A porta ${porta} já está em uso. Rode com --porta OUTRA.\n\n`,
      );
    } else {
      process.stderr.write(`\n  Falha ao iniciar o servidor: ${erro.message}\n\n`);
    }
    process.exitCode = 1;
  });

  const encerrar = () => {
    process.stdout.write("\n  Encerrando...\n");
    servidor.close(() => process.exit(0));
  };
  process.on("SIGINT", encerrar);
  process.on("SIGTERM", encerrar);

  return servidor;
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  try {
    iniciar(process.argv.slice(2));
  } catch (erro) {
    process.stderr.write(`${erro.message}\n`);
    process.exitCode = 2;
  }
}

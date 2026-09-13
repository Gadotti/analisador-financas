/** Utilitários compartilhados pelos testes da aplicação Node. */

import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { gerarHashSenha } from "../../src/core/authService.js";

/**
 * Aponta PORTFOLIO_DATA_DIR para um diretório temporário exclusivo do teste
 * e devolve uma função que restaura o ambiente e apaga os arquivos.
 */
export function dataDirTemporario() {
  const anterior = process.env.PORTFOLIO_DATA_DIR;
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "analisador-"));
  fs.mkdirSync(path.join(dir, "history"), { recursive: true });
  process.env.PORTFOLIO_DATA_DIR = dir;

  return {
    dir,
    limpar() {
      if (anterior === undefined) delete process.env.PORTFOLIO_DATA_DIR;
      else process.env.PORTFOLIO_DATA_DIR = anterior;
      fs.rmSync(dir, { recursive: true, force: true });
    },
  };
}

/**
 * Isola a configuração de IA num .env temporário, apontado por IA_ENV_FILE.
 *
 * Sem isso os testes leriam o .env real do projeto, com a chave e o modelo do
 * usuário. `escrever` grava as variáveis; `limpar` restaura e apaga.
 */
export function envIaTemporario(variaveis = null) {
  const anterior = process.env.IA_ENV_FILE;
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "analisador-ia-"));
  const arquivo = path.join(dir, "ia.env");
  process.env.IA_ENV_FILE = arquivo;

  function escrever(valores) {
    const linhas = Object.entries(valores).map(([chave, valor]) => `${chave}=${valor}`);
    fs.writeFileSync(arquivo, linhas.join(os.EOL), "utf8");
  }

  if (variaveis) escrever(variaveis);

  return {
    arquivo,
    escrever,
    limpar() {
      if (anterior === undefined) delete process.env.IA_ENV_FILE;
      else process.env.IA_ENV_FILE = anterior;
      fs.rmSync(dir, { recursive: true, force: true });
    },
  };
}

/**
 * Isola as credenciais de login num .env temporário, apontado por
 * AUTH_ENV_FILE — mesmo papel de envIaTemporario() para a configuração de IA.
 */
export function authEnvTemporario(variaveis = null) {
  const anterior = process.env.AUTH_ENV_FILE;
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "analisador-auth-"));
  const arquivo = path.join(dir, "auth.env");
  process.env.AUTH_ENV_FILE = arquivo;

  function escrever(valores) {
    const linhas = Object.entries(valores).map(([chave, valor]) => `${chave}=${valor}`);
    fs.writeFileSync(arquivo, linhas.join(os.EOL), "utf8");
  }

  if (variaveis) escrever(variaveis);

  return {
    arquivo,
    escrever,
    limpar() {
      if (anterior === undefined) delete process.env.AUTH_ENV_FILE;
      else process.env.AUTH_ENV_FILE = anterior;
      fs.rmSync(dir, { recursive: true, force: true });
    },
  };
}

/** Usuário e senha de teste prontos, já com o hash que vai no .env temporário. */
export function credenciaisAuthExemplo(usuario = "teste", senha = "senha-teste-123") {
  return {
    usuario,
    senha,
    variaveis: {
      AUTH_USUARIO: usuario,
      AUTH_SENHA_HASH: gerarHashSenha(senha),
      AUTH_SESSAO_SEGREDO: "segredo-de-teste-para-assinatura-hmac",
    },
  };
}

/** Define variáveis de ambiente e devolve um restaurador. */
export function comEnv(valores) {
  const anteriores = {};
  for (const [chave, valor] of Object.entries(valores)) {
    anteriores[chave] = process.env[chave];
    if (valor === undefined) delete process.env[chave];
    else process.env[chave] = valor;
  }
  return () => {
    for (const [chave, valor] of Object.entries(anteriores)) {
      if (valor === undefined) delete process.env[chave];
      else process.env[chave] = valor;
    }
  };
}

/** Snapshot no formato que o script Python grava, para alimentar os testes. */
export function snapshotExemplo(sobrescreve = {}) {
  return {
    gerado_em: "2026-09-01T10:30:00",
    data: "2026-09-01",
    perfil: "Renda mensal com risco moderado.",
    totais: {
      valor_investido: 20000,
      valor_atual: 22000,
      resultado: 2000,
      resultado_pct: 10,
      resultado_dia: 35.5,
      posicoes: 2,
    },
    classes: {
      fii: {
        rotulo: "FIIs",
        posicoes: 1,
        valor_investido: 10000,
        valor_atual: 12000,
        resultado: 2000,
        resultado_pct: 20,
        peso_pct: 54.55,
      },
    },
    posicoes: [],
    alertas: [],
    saude_carteira: "boa",
    destaques: { melhores: [], piores: [] },
    macro: {
      cdi_anual_pct: { valor: 14.9 },
      selic_meta_pct: { valor: 15 },
      ipca_12m_pct: { valor: 4.2 },
      indices: {},
    },
    ...sobrescreve,
  };
}

/** Grava um registro de análise como o script Python faria. */
export function gravarAnalise(dir, snapshot) {
  const registro = {
    gerado_em: snapshot.gerado_em,
    snapshot,
    ia: null,
    fundamentos: null,
    ia_erro: null,
    ia_solicitada: false,
  };
  const conteudo = JSON.stringify(registro, null, 2);
  fs.mkdirSync(path.join(dir, "history"), { recursive: true });
  fs.writeFileSync(path.join(dir, "last_analysis.json"), conteudo, "utf8");
  fs.writeFileSync(path.join(dir, "history", `${snapshot.data}.json`), conteudo, "utf8");
  return registro;
}

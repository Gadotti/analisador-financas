/**
 * Ponte entre o servidor web e o script de análise em Python.
 *
 * O servidor nunca chama a API de IA nem o Telegram: ele dispara
 * `scripts/analisar.py` como processo filho e lê o JSON do stdout. Assim a
 * mesma execução vale para o agendador de tarefas, para o terminal e para o
 * botão da interface.
 */

import { spawn } from "node:child_process";

import { BASE_DIR, SCRIPT_ANALISE } from "../config/paths.js";

export const TIMEOUT_PADRAO_MS = 10 * 60 * 1000;

/**
 * Interpretador Python a usar.
 *
 * Respeita PYTHON_BIN quando definido (útil para apontar para o venv);
 * senão usa `python` no Windows e `python3` nos demais sistemas.
 */
export function interpretadorPython() {
  return process.env.PYTHON_BIN || (process.platform === "win32" ? "python" : "python3");
}

/**
 * Roda o script isolado e devolve o JSON que ele imprimiu.
 *
 * @param {string[]} args                  Flags do script (`--json` é sempre adicionada).
 * @param {number}   [opcoes.timeoutMs]
 * @param {Function} [opcoes.aoRegistrar]  Recebe cada linha de progresso (stderr).
 * @param {string}   [opcoes.script]       Caminho alternativo do script.
 * @param {string}   [opcoes.python]       Interpretador alternativo.
 */
export function rodarScript(
  args = [],
  {
    timeoutMs = TIMEOUT_PADRAO_MS,
    aoRegistrar = null,
    script = SCRIPT_ANALISE,
    python = null,
  } = {},
) {
  return new Promise((resolve, reject) => {
    const executavel = python || interpretadorPython();

    const filho = spawn(executavel, [script, "--json", ...args], {
      cwd: BASE_DIR,
      // PYTHONIOENCODING garante UTF-8 no stdout mesmo em consoles Windows legados.
      env: { ...process.env, PYTHONIOENCODING: "utf-8" },
      windowsHide: true,
    });

    let saida = "";
    let erroTexto = "";
    let expirou = false;

    const relogio = setTimeout(() => {
      expirou = true;
      filho.kill();
    }, timeoutMs);

    filho.stdout.setEncoding("utf8");
    filho.stderr.setEncoding("utf8");
    filho.stdout.on("data", (pedaco) => {
      saida += pedaco;
    });
    filho.stderr.on("data", (pedaco) => {
      erroTexto += pedaco;
      if (aoRegistrar) {
        for (const linha of String(pedaco).split(/\r?\n/)) {
          if (linha.trim()) aoRegistrar(linha.trimEnd());
        }
      }
    });

    filho.on("error", (erro) => {
      clearTimeout(relogio);
      const detalhe =
        erro.code === "ENOENT"
          ? `Python não encontrado ('${executavel}'). Instale o Python 3.10+ ou defina PYTHON_BIN no .env.`
          : erro.message;
      reject(new Error(`Não foi possível iniciar a análise: ${detalhe}`));
    });

    filho.on("close", (codigo) => {
      clearTimeout(relogio);

      if (expirou) {
        reject(new Error("A análise excedeu o tempo limite e foi interrompida."));
        return;
      }

      const bruto = saida.trim();
      if (!bruto) {
        const detalhe = erroTexto.trim().split(/\r?\n/).slice(-3).join(" ");
        reject(
          new Error(
            `A análise terminou com código ${codigo} sem produzir resultado. ${detalhe}`.trim(),
          ),
        );
        return;
      }

      let dados;
      try {
        // A última linha do stdout é o JSON; o resto é ruído eventual.
        dados = JSON.parse(bruto.split(/\r?\n/).pop());
      } catch (erro) {
        reject(new Error(`A análise devolveu uma saída inválida: ${erro.message}`));
        return;
      }

      if (dados && dados.erro) {
        reject(new Error(dados.erro));
        return;
      }
      resolve(dados);
    });
  });
}

/** Executa a análise completa (com ou sem IA). */
export function executarAnalise({ usarIa = true, ...opcoes } = {}) {
  return rodarScript(usarIa ? [] : ["--sem-ia"], opcoes);
}

/** Reenvia ao Telegram a última análise salva. */
export function enviarUltimaAoTelegram(opcoes = {}) {
  return rodarScript(["--enviar-ultima"], opcoes);
}

/** Testa a conexão com o bot do Telegram. */
export function testarTelegram(opcoes = {}) {
  return rodarScript(["--testar-telegram"], opcoes);
}

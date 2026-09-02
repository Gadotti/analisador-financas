/**
 * Leitura da configuração de IA declarada no .env — do lado do Node.
 *
 * O servidor não chama a API de IA (isso é do script Python); ele só precisa
 * saber se a configuração está completa, para habilitar os botões e mostrar
 * provedor e modelo no rodapé. As regras são as mesmas de `analise/config_ia.py`,
 * porque as duas metades leem o **mesmo** arquivo: o `.env` tem precedência
 * sobre o ambiente, e cada provedor tem seu bloco prefixado pelo nome
 * (`IA_PROVEDOR=kimi` lê `KIMI_MODEL`, `KIMI_EFFORT`, ...).
 *
 * A chave da API nunca é devolvida daqui: o Node confere apenas a presença.
 */

import { lerArquivoEnv } from "../util/env.js";
import { BASE_DIR } from "./paths.js";
import path from "node:path";

export const PROVEDOR_PADRAO = "anthropic";
export const ORIGEM_PADRAO = "arquivo";
export const ORIGENS = ["arquivo", "ambiente"];
export const EFFORT_NENHUM = "nenhum";

/** Configuração de IA incompleta ou inválida no .env. */
export class ConfiguracaoIaError extends Error {
  constructor(mensagem) {
    super(mensagem);
    this.name = "ConfiguracaoIaError";
  }
}

/** Arquivo .env em uso. IA_ENV_FILE redireciona (é assim que os testes isolam). */
export function arquivoEnvIa() {
  return process.env.IA_ENV_FILE || path.join(BASE_DIR, ".env");
}

function valor(doArquivo, nome) {
  return (doArquivo[nome] || "").trim() || (process.env[nome] || "").trim();
}

function exigir(doArquivo, nome, ajuda) {
  const lido = valor(doArquivo, nome);
  if (!lido) {
    throw new ConfiguracaoIaError(`${nome} não definida em ${arquivoEnvIa()}. ${ajuda}`);
  }
  return lido;
}

/** Prefixo das variáveis do provedor: "kimi" -> "KIMI_". */
export function prefixoProvedor(provedor) {
  const limpo = provedor
    .replace(/[^A-Za-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .toUpperCase();
  if (!limpo) {
    throw new ConfiguracaoIaError(
      `IA_PROVEDOR inválido: "${provedor}". Use um nome simples, como "anthropic" ou "kimi".`,
    );
  }
  return `${limpo}_`;
}

function origemChave(doArquivo, prefixo) {
  const origem = (valor(doArquivo, `${prefixo}ORIGEM_CHAVE`) || ORIGEM_PADRAO).toLowerCase();
  if (!ORIGENS.includes(origem)) {
    throw new ConfiguracaoIaError(
      `${prefixo}ORIGEM_CHAVE inválida: "${origem}". Use um destes valores: ${ORIGENS.join(", ")}.`,
    );
  }
  return origem;
}

function conferirChave(doArquivo, prefixo, origem) {
  if (origem === "arquivo") {
    // Origem "arquivo": a chave é lida somente do .env, nunca do ambiente.
    if (!(doArquivo[`${prefixo}API_KEY`] || "").trim()) {
      throw new ConfiguracaoIaError(
        `${prefixo}API_KEY não encontrada em ${arquivoEnvIa()}. Com ` +
          `${prefixo}ORIGEM_CHAVE=arquivo a chave é lida somente do arquivo .env.`,
      );
    }
    return;
  }
  const nomeVar = exigir(
    doArquivo,
    `${prefixo}VARIAVEL_CHAVE`,
    `Com ${prefixo}ORIGEM_CHAVE=ambiente, informe nela o nome da variável de ` +
      "ambiente que guarda a chave.",
  );
  if (!(process.env[nomeVar] || "").trim()) {
    throw new ConfiguracaoIaError(
      `A variável de ambiente ${nomeVar} (indicada em ${prefixo}VARIAVEL_CHAVE) ` +
        "está vazia ou não existe.",
    );
  }
}

/**
 * Configuração do provedor ativo. Lança ConfiguracaoIaError quando falta algo.
 * @param {boolean} [opcoes.exigirChave] false para descrever provedor, modelo e
 *   esforço sem depender da credencial.
 */
export function configuracaoIa({ exigirChave = true } = {}) {
  const doArquivo = lerArquivoEnv(arquivoEnvIa());
  const provedor = valor(doArquivo, "IA_PROVEDOR") || PROVEDOR_PADRAO;
  const prefixo = prefixoProvedor(provedor);

  const modelo = exigir(
    doArquivo,
    `${prefixo}MODEL`,
    `Defina nela o modelo do provedor "${provedor}".`,
  );
  const esforco = exigir(
    doArquivo,
    `${prefixo}EFFORT`,
    `Defina nela o esforço do provedor "${provedor}" (low, medium, high, xhigh, max) ` +
      `ou "${EFFORT_NENHUM}" para não enviar o campo.`,
  );
  const origem = origemChave(doArquivo, prefixo);
  if (exigirChave) conferirChave(doArquivo, prefixo, origem);

  return {
    provedor: provedor.toLowerCase(),
    prefixo,
    modelo,
    effort: esforco.toLowerCase() === EFFORT_NENHUM ? null : esforco,
    origemChave: origem,
  };
}

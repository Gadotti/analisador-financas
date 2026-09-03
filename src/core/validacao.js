/**
 * Validadores dos campos de uma posição da carteira.
 *
 * Vivem separados do CRUD porque as regras de renda variável e de renda fixa
 * compartilham as mesmas conversões — e a mensagem de erro precisa ser a mesma
 * em qualquer uma delas.
 */

import { paraData, paraISO } from "../util/datas.js";

/** Erro de validação de uma posição da carteira. */
export class ValidacaoError extends Error {
  constructor(mensagem) {
    super(mensagem);
    this.name = "ValidacaoError";
  }
}

export function numero(valor, campo, { minimo = null } = {}) {
  if (valor === null || valor === undefined || valor === "") {
    throw new ValidacaoError(`Campo '${campo}' e obrigatorio.`);
  }
  const n = Number(String(valor).replace(",", "."));
  if (!Number.isFinite(n)) {
    throw new ValidacaoError(`Campo '${campo}' deve ser numerico.`);
  }
  if (minimo !== null && n < minimo) {
    throw new ValidacaoError(`Campo '${campo}' deve ser >= ${minimo}.`);
  }
  return n;
}

export function data(valor, campo, { obrigatorio = true } = {}) {
  if (!valor) {
    if (obrigatorio) {
      throw new ValidacaoError(`Campo '${campo}' e obrigatorio (formato AAAA-MM-DD).`);
    }
    return null;
  }
  try {
    return paraISO(paraData(valor));
  } catch {
    throw new ValidacaoError(`Campo '${campo}' invalido - use AAAA-MM-DD.`);
  }
}

export function texto(valor, campo, { obrigatorio = true } = {}) {
  const txt = valor === null || valor === undefined ? "" : String(valor).trim();
  if (obrigatorio && !txt) throw new ValidacaoError(`Campo '${campo}' e obrigatorio.`);
  return txt;
}

/**
 * Valor de uma lista fechada.
 *
 * @param {string} rotulo Como o campo aparece na mensagem de erro ("Indexador").
 * @param {Function} ajustar Normalização aplicada antes de conferir a lista.
 */
export function opcao(valor, campo, permitidos, { rotulo, ajustar = (v) => v } = {}) {
  const escolhido = ajustar(texto(valor, campo));
  if (!permitidos.includes(escolhido)) {
    throw new ValidacaoError(
      `${rotulo || `Campo '${campo}'`} invalido: '${escolhido}'. Use: ${permitidos.join(", ")}.`,
    );
  }
  return escolhido;
}

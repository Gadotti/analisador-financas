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

export function numero(
  valor,
  campo,
  { minimo = null, maximo = null, obrigatorio = true } = {},
) {
  if (valor === null || valor === undefined || valor === "") {
    if (!obrigatorio) return null;
    throw new ValidacaoError(`Campo '${campo}' e obrigatorio.`);
  }
  const n = Number(String(valor).replace(",", "."));
  if (!Number.isFinite(n)) {
    throw new ValidacaoError(`Campo '${campo}' deve ser numerico.`);
  }
  if (minimo !== null && n < minimo) {
    throw new ValidacaoError(`Campo '${campo}' deve ser >= ${minimo}.`);
  }
  if (maximo !== null && n > maximo) {
    throw new ValidacaoError(`Campo '${campo}' deve ser <= ${maximo}.`);
  }
  return n;
}

/**
 * Booleano de um formulário.
 *
 * Aceita o que o HTML entrega de fato: um checkbox marcado vira `true`, mas um
 * `<select>` ou um campo de texto entregam a string "true"/"false" — e
 * `Boolean("false")` seria `true`.
 */
export function booleano(valor, campo) {
  if (typeof valor === "boolean") return valor;
  const txt = String(valor ?? "").trim().toLowerCase();
  if (["true", "1", "sim", "on"].includes(txt)) return true;
  if (["false", "0", "nao", "não", "off", ""].includes(txt)) return false;
  throw new ValidacaoError(`Campo '${campo}' deve ser verdadeiro ou falso, e nao '${valor}'.`);
}

/**
 * Lista de inteiros, vinda de um array ou de um texto separado por vírgulas.
 *
 * Os marcos de calendário e os dias da semana são digitados como "30, 15, 7"
 * numa tela e chegam como array em outra; a conversão é a mesma.
 */
export function listaDeInteiros(valor, campo, { minimo = 0, maximo = null } = {}) {
  const bruto = Array.isArray(valor) ? valor : String(valor ?? "").split(",");
  const numeros = bruto
    .map((item) => String(item).trim())
    .filter((item) => item !== "")
    .map((item) => numero(item, campo, { minimo }));

  for (const n of numeros) {
    if (!Number.isInteger(n) || (maximo !== null && n > maximo)) {
      throw new ValidacaoError(
        `Campo '${campo}' aceita inteiros de ${minimo} a ${maximo ?? "∞"}, e recebeu '${n}'.`,
      );
    }
  }
  // A ordem digitada é preservada: quem consome trata a lista como conjunto, e
  // reordenar só faria o campo voltar diferente do que o usuário escreveu.
  return [...new Set(numeros)];
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

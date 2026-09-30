/**
 * O que a tela guarda no DOM e um redesenho apagaria.
 *
 * As telas se desenham por `innerHTML`; uma atualização em segundo plano não pode
 * fechar o que o usuário abriu nem roubar a vez de quem está digitando.
 */

import { $$ } from "./formato.js";

const CAMPOS_DE_ENTRADA = ["INPUT", "TEXTAREA", "SELECT"];

const rotuloDaDobra = (dobra) => dobra.querySelector("summary")?.textContent.trim() ?? "";

/**
 * Executa o redesenho mantendo abertas as dobras (`<details>`) que estavam
 * abertas, reconhecidas pelo texto do `summary`.
 */
export function preservandoDobras(redesenhar) {
  const abertas = new Set($$("details[open]").map(rotuloDaDobra).filter(Boolean));
  redesenhar();
  if (abertas.size === 0) return;
  $$("details").forEach((dobra) => {
    if (abertas.has(rotuloDaDobra(dobra))) dobra.open = true;
  });
}

/** O foco está num campo de texto, seletor ou caixa de marcar? */
export function digitandoEmCampo(documento = document) {
  const ativo = documento.activeElement;
  return Boolean(ativo) && CAMPOS_DE_ENTRADA.includes(ativo.tagName);
}

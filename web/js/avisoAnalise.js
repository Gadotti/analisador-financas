/** Pílula "há uma leitura mais nova": aparece só quando a tela não pôde atualizar sozinha. */

import { $ } from "./formato.js";

/** "09:32" a partir de um instante ISO; vazio se a data não for válida. */
export function horaDaAtualizacao(iso) {
  if (!iso) return "";
  const instante = new Date(iso);
  if (Number.isNaN(instante.getTime())) return "";
  return instante.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

/** @param {{atualizada_em: string}|null} aviso `null` esconde a pílula. */
export function renderAvisoAnalise(aviso) {
  const pilula = $("#pilula-analise");
  if (!aviso) {
    pilula.classList.add("hidden");
    return;
  }
  const hora = horaDaAtualizacao(aviso.atualizada_em);
  pilula.textContent = hora ? `Nova leitura das ${hora} — atualizar` : "Nova leitura — atualizar";
  pilula.classList.remove("hidden");
}

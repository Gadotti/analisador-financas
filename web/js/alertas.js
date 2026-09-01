/**
 * Cartão de alerta — a mesma anatomia para riscos do cálculo, riscos da IA,
 * fatos recentes e pontos de observação, que dividem a tela na Visão geral.
 */

import { esc } from "./formato.js";
import { iconeSeveridade } from "./icones.js";

export const cartaoAlerta = (severidade, titulo, descricao, fonte = "") => `
  <div class="alerta alerta-${severidade || "info"}">
    <span class="alerta-icone">${iconeSeveridade(severidade)}</span>
    <div>
      <div class="alerta-titulo">${titulo}</div>
      <div class="alerta-desc">${descricao}</div>
      ${fonte ? `<div class="alerta-fonte">${fonte}</div>` : ""}
    </div>
  </div>`;

/** Bloco com subtítulo e os cartões; string vazia quando não há item algum. */
export function listaAlertas(titulo, itens, comAtivo = false) {
  if (!itens?.length) return "";

  const cartoes = itens
    .map((i) =>
      cartaoAlerta(
        i.severidade,
        comAtivo && i.ativo ? `[${esc(i.ativo)}] ${esc(i.titulo)}` : esc(i.titulo),
        esc(i.descricao),
        i.fonte ? `Fonte: ${esc(i.fonte)}` : rotuloAtivos(i)
      )
    )
    .join("");

  return `<div class="subtitulo">${titulo}</div><div class="alertas">${cartoes}</div>`;
}

const rotuloAtivos = (item) => (item.ativos?.length ? esc(item.ativos.join(", ")) : "");

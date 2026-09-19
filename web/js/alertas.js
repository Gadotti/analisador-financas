/**
 * Cartão de alerta — a mesma anatomia para riscos do cálculo, riscos da IA,
 * fatos recentes e pontos de observação, que dividem a tela na Visão geral.
 *
 * Há duas formas: a aberta, para o aviso solitário que precisa ser lido de
 * imediato, e a colapsável, para as listas — onde o título já resume o caso e
 * a descrição só interessa a quem for atrás dela.
 */

import { esc } from "./formato.js";
import { icone, iconeSeveridade } from "./icones.js";

const corpo = (descricao, fonte) =>
  `<div class="alerta-desc">${descricao}</div>` +
  (fonte ? `<div class="alerta-fonte">${fonte}</div>` : "");

export const cartaoAlerta = (severidade, titulo, descricao, fonte = "") => `
  <div class="alerta alerta-${severidade || "info"}">
    <span class="alerta-icone">${iconeSeveridade(severidade)}</span>
    <div>
      <div class="alerta-titulo">${titulo}</div>
      ${corpo(descricao, fonte)}
    </div>
  </div>`;

/** Selo discreto: este texto já saiu numa mensagem do Telegram, sem mudar desde então. */
const seloEnviado = (enviado) =>
  enviado
    ? `<span class="alerta-enviado" title="Já enviado ao Telegram, sem mudança desde então">${icone("enviado", 13)}</span>`
    : "";

/** Recolhido por padrão: só o título aparece até o usuário abrir o cartão. */
export const cartaoAlertaRecolhido = (severidade, titulo, descricao, fonte = "", enviado = false) => `
  <details class="alerta alerta-recolhivel alerta-${severidade || "info"}">
    <summary>
      <span class="alerta-icone">${iconeSeveridade(severidade)}</span>
      <span class="alerta-titulo">${titulo}</span>
      ${seloEnviado(enviado)}
      <span class="alerta-seta">${icone("seta", 16)}</span>
    </summary>
    <div class="alerta-corpo">${corpo(descricao, fonte)}</div>
  </details>`;

/** Bloco com subtítulo e os cartões; string vazia quando não há item algum. */
export function listaAlertas(titulo, itens, comAtivo = false) {
  if (!itens?.length) return "";

  const cartoes = itens
    .map((i) =>
      cartaoAlertaRecolhido(
        i.severidade,
        comAtivo && i.ativo ? `[${esc(i.ativo)}] ${esc(i.titulo)}` : esc(i.titulo),
        esc(i.descricao),
        i.fonte ? `Fonte: ${esc(i.fonte)}` : rotuloAtivos(i),
        i.enviado_telegram
      )
    )
    .join("");

  return `<div class="subtitulo">${titulo}</div><div class="alertas">${cartoes}</div>`;
}

const rotuloAtivos = (item) => (item.ativos?.length ? esc(item.ativos.join(", ")) : "");

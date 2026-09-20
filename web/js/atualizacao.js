/** Barra de aviso: nova versão publicada, lida de `GET /api/atualizacao`. */

import { $ } from "./formato.js";

export function renderAtualizacao(dados) {
  const banner = $("#banner-versao");
  if (!dados?.disponivel) {
    banner.classList.add("hidden");
    return;
  }

  $("#banner-versao-texto").textContent =
    `Nova versão disponível: ${dados.versao_disponivel} (você está na ${dados.versao_atual}).`;
  $("#banner-versao-link").href = dados.url || "#";
  banner.classList.remove("hidden");
}

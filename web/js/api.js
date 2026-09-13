/** Acesso à API local e avisos ao usuário. */

import { $ } from "./formato.js";

export async function api(rota, opcoes = {}) {
  const resposta = await fetch(rota, {
    headers: { "Content-Type": "application/json" },
    ...opcoes,
  });

  if (resposta.status === 401) {
    location.href = "/login";
    throw new Error("Autenticação necessária.");
  }

  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(dados.erro || `Erro ${resposta.status}`);
  return dados;
}

export function toast(mensagem, tipo = "info", duracao = 4500) {
  const el = document.createElement("div");
  el.className = `toast toast-${tipo}`;
  el.textContent = mensagem;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), duracao);
}

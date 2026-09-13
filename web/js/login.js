/**
 * Tela de login — único ponto do front que fala com /api/auth/login.
 *
 * `login` fica separado de `ligarFormulario` para poder ser testado sem DOM,
 * no mesmo padrão de coletarX/ligarX dos outros módulos da tela.
 */

import { $ } from "./formato.js";

const ERRO_PADRAO = "Usuário ou senha inválidos.";

/** Faz a chamada de login; lança com a mensagem do servidor em caso de falha. */
export async function login(usuario, senha) {
  const resposta = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ usuario, senha }),
  });
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(dados.erro || ERRO_PADRAO);
  return dados;
}

export function ligarFormulario() {
  const form = $("#form-login");
  const erro = $("#login-erro");
  const botao = $("#login-btn");

  form.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    erro.classList.add("hidden");
    botao.disabled = true;

    try {
      await login($("#login-usuario").value.trim(), $("#login-senha").value);
      location.href = "/";
    } catch (falha) {
      erro.textContent = falha.message;
      erro.classList.remove("hidden");
      botao.disabled = false;
    }
  });
}

if (typeof document !== "undefined" && document.getElementById("form-login")) {
  ligarFormulario();
}

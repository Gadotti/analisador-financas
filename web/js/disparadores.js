/**
 * Tela "Disparadores" — documentação e atalhos para as formas de rodar
 * `scripts/analisar.py`. Os botões de ação reaproveitam as mesmas rotas que
 * o topo da página já usa; os de "Copiar" só levam o comando à área de
 * transferência, para colar no terminal ou no Agendador de Tarefas.
 */

import { api, toast } from "./api.js";
import { $, $$ } from "./formato.js";

async function testarTelegram() {
  const botao = $("#btn-disp-telegram-testar");
  botao.disabled = true;
  try {
    const resultado = await api("/api/telegram/testar", { method: "POST" });
    toast(`Conectado — bot "${resultado.bot}" respondeu.`, "ok");
  } catch (erro) {
    toast(erro.message, "erro", 7000);
  } finally {
    botao.disabled = false;
  }
}

async function testarIa() {
  const botao = $("#btn-disp-ia-testar");
  const provedor = $("#disp-ia-provedor").value;
  botao.disabled = true;
  try {
    const resultado = await api("/api/ia/testar", {
      method: "POST",
      body: JSON.stringify({ provedor }),
    });
    toast(`Conectado — ${resultado.modelo} respondeu.`, "ok");
  } catch (erro) {
    toast(erro.message, "erro", 7000);
  } finally {
    botao.disabled = false;
  }
}

async function copiarComando(botao) {
  const comando = botao.dataset.comando;
  try {
    await navigator.clipboard.writeText(comando);
    toast("Comando copiado.", "ok", 2500);
  } catch {
    toast("Não foi possível copiar — copie o comando manualmente.", "erro");
  }
}

/**
 * @param {object} acoes
 * @param {(comIa: boolean) => Promise<void>} acoes.rodarAnalise Já usado pelos botões do topo.
 * @param {() => Promise<void>} acoes.enviarAoTelegram Idem.
 */
export function ligarDisparadores({ rodarAnalise, enviarAoTelegram }) {
  $("#btn-disp-analise-ia").addEventListener("click", () => rodarAnalise(true));
  $("#btn-disp-cotacoes").addEventListener("click", () => rodarAnalise(false));
  $("#btn-disp-telegram-enviar").addEventListener("click", enviarAoTelegram);
  $("#btn-disp-telegram-testar").addEventListener("click", testarTelegram);
  $("#btn-disp-ia-testar").addEventListener("click", testarIa);
  $$(".btn-copiar").forEach((botao) => botao.addEventListener("click", () => copiarComando(botao)));
}

/** Espelha o mesmo status que habilita os botões do topo (`aplicarStatus`). */
export function aplicarStatusDisparadores(status) {
  $("#btn-disp-analise-ia").disabled = !status.ia_disponivel;
  $("#btn-disp-ia-testar").disabled = !status.ia_disponivel;
  $("#btn-disp-telegram-enviar").disabled = !status.telegram_configurado;
  $("#btn-disp-telegram-testar").disabled = !status.telegram_configurado;
}

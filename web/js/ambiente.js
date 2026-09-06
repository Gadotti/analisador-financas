/**
 * Tela "Configurações": provedor de IA, Telegram e brapi.
 *
 * Grava direto no .env, pelo /api/ambiente. Os campos de segredo (chave de
 * API, token do bot) nunca vêm preenchidos — só um selo indica se já há um
 * valor salvo; deixá-los em branco no envio mantém o que já está gravado.
 */

import { $, mostrar } from "./formato.js";

const PROVEDORES = ["anthropic", "kimi"];

const SELETOR_CAMPO = {
  origem_chave: (p) => `#e-${p}-origem`,
  variavel_chave: (p) => `#e-${p}-variavel`,
  model: (p) => `#e-${p}-modelo`,
  effort: (p) => `#e-${p}-effort`,
  base_url: (p) => `#e-${p}-url`,
  fallback: (p) => `#e-${p}-fallback`,
  busca_web: (p) => `#e-${p}-busca`,
  max_tokens: (p) => `#e-${p}-tokens`,
};

function pintarSelo(el, definida) {
  if (!el) return;
  el.textContent = definida ? "chave configurada" : "sem chave";
  el.className = `selo ${definida ? "selo-otima" : "selo-alerta"}`;
}

function alternarVariavel(provedor) {
  const origem = $(`#e-${provedor}-origem`).value;
  mostrar(`.campo-variavel-${provedor}`, origem === "ambiente");
}

export function renderAmbiente(dados) {
  $("#e-provedor").value = dados.ia_provedor || "anthropic";

  for (const nome of PROVEDORES) {
    const bloco = dados.provedores[nome];
    for (const [campo, seletor] of Object.entries(SELETOR_CAMPO)) {
      const el = $(seletor(nome));
      if (el) el.value = bloco[campo] ?? "";
    }
    $(`#e-${nome}-chave`).value = "";
    pintarSelo($(`#e-${nome}-chave-selo`), bloco.api_key_definida);
    alternarVariavel(nome);
  }

  $("#e-telegram-chat").value = dados.telegram.chat_id || "";
  $("#e-telegram-token").value = "";
  pintarSelo($("#e-telegram-token-selo"), dados.telegram.bot_token_definido);

  $("#e-brapi-token").value = "";
  pintarSelo($("#e-brapi-token-selo"), dados.brapi_token_definido);
}

/** Lê a tela no formato que /api/ambiente espera. */
export function coletarAmbiente() {
  const provedores = {};
  for (const nome of PROVEDORES) {
    const bloco = { api_key: $(`#e-${nome}-chave`).value };
    for (const [campo, seletor] of Object.entries(SELETOR_CAMPO)) {
      bloco[campo] = $(seletor(nome)).value;
    }
    provedores[nome] = bloco;
  }

  return {
    ia_provedor: $("#e-provedor").value,
    provedores,
    telegram: {
      chat_id: $("#e-telegram-chat").value,
      bot_token: $("#e-telegram-token").value,
    },
    brapi_token: $("#e-brapi-token").value,
  };
}

export function ligarAmbiente() {
  for (const nome of PROVEDORES) {
    $(`#e-${nome}-origem`).addEventListener("change", () => alternarVariavel(nome));
  }
}

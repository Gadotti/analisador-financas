/**
 * Tela "Configurações": provedor de IA, Telegram e brapi.
 *
 * Grava direto no .env, pelo /api/ambiente. Os campos de segredo (chave de
 * API, token do bot) nunca vêm preenchidos — só um selo indica se já há um
 * valor salvo; deixá-los em branco no envio mantém o que já está gravado.
 */

import { api } from "./api.js";
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
  el.textContent = definida ? "chave salva" : "nenhuma chave salva";
  el.className = `chave-selo ${definida ? "chave-selo-ok" : ""}`.trim();
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
    pintarResultadoTeste(nome, "", null);
  }

  $("#e-telegram-chat").value = dados.telegram.chat_id || "";
  $("#e-telegram-token").value = "";
  pintarSelo($("#e-telegram-token-selo"), dados.telegram.bot_token_definido);
  pintarResultadoTeste("telegram", "", null);

  $("#e-brapi-token").value = "";
  pintarSelo($("#e-brapi-token-selo"), dados.brapi_token_definido);
}

/** Lê a tela no formato que /api/ambiente espera. */
export function coletarAmbiente() {
  const provedores = {};
  for (const nome of PROVEDORES) {
    const bloco = { api_key: $(`#e-${nome}-chave`).value };
    for (const [campo, seletor] of Object.entries(SELETOR_CAMPO)) {
      // Nem todo provedor tem campo na tela (ex.: Kimi não tem fallback nem busca web).
      const el = $(seletor(nome));
      if (el) bloco[campo] = el.value;
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

/** `estado` é "ok" | "erro" | "aviso" | null (null limpa, sem cor). */
function pintarResultadoTeste(chave, texto, estado) {
  const el = $(`#e-${chave}-teste-resultado`);
  if (!el) return;
  el.textContent = texto;
  el.className = `teste-status ${estado ? `teste-status-${estado}` : ""}`.trim();
}

/**
 * Testa uma conexão e pinta o resultado ao lado do botão. `chamar` faz a
 * requisição e devolve `{ texto, estado }`; erros (rede, configuração
 * ausente) caem no `catch` e aparecem como aviso de erro.
 */
async function executarTeste(chave, chamar) {
  const botao = $(`#btn-testar-${chave}`);
  const original = botao.innerHTML;
  botao.disabled = true;
  botao.innerHTML = '<span class="girando"></span>Testando…';
  pintarResultadoTeste(chave, "", null);

  try {
    const { texto, estado } = await chamar();
    pintarResultadoTeste(chave, texto, estado);
  } catch (erro) {
    pintarResultadoTeste(chave, erro.message, "erro");
  } finally {
    botao.disabled = false;
    botao.innerHTML = original;
  }
}

/** Ping mínimo à API do provedor: só confirma que a chave e o modelo respondem. */
function testarConexaoIa(provedor) {
  return executarTeste(provedor, async () => {
    const resultado = await api("/api/ia/testar", {
      method: "POST",
      body: JSON.stringify({ provedor }),
    });
    return resultado.truncado
      ? {
          texto:
            "Conectado — o pong veio cortado pelo teto baixo deste teste (normal em modelos com " +
            "raciocínio interno, como o Kimi). A análise completa usa um teto bem maior e não é afetada.",
          estado: "aviso",
        }
      : { texto: `Conectado — ${resultado.modelo} respondeu.`, estado: "ok" };
  });
}

/** Confirma o token do bot e envia uma mensagem de teste ao chat configurado. */
function testarConexaoTelegram() {
  return executarTeste("telegram", async () => {
    const resultado = await api("/api/telegram/testar", { method: "POST" });
    return { texto: `Conectado — bot "${resultado.bot}" respondeu.`, estado: "ok" };
  });
}

export function ligarAmbiente() {
  for (const nome of PROVEDORES) {
    $(`#e-${nome}-origem`).addEventListener("change", () => alternarVariavel(nome));
    $(`#btn-testar-${nome}`).addEventListener("click", () => testarConexaoIa(nome));
  }
  $("#btn-testar-telegram").addEventListener("click", testarConexaoTelegram);
}

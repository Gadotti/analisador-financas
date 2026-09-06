/**
 * Portfolio Analyzer — ponto de entrada da interface local.
 *
 * Só orquestra: carrega os dados da API, guarda o último resultado e manda
 * cada módulo desenhar a sua parte. Nenhuma regra de cálculo mora aqui.
 */

import { api, toast } from "./js/api.js";
import { renderAnaliseVazia, renderFichas, renderLeitura } from "./js/analiseIa.js";
import { renderAlocacao } from "./js/alocacao.js";
import { coletarConfig, renderConfig } from "./js/configuracoes.js";
import { ligarEquivalencia, renderEquivalencia } from "./js/equivalencia.js";
import { $, $$ } from "./js/formato.js";
import { renderHistorico } from "./js/historico.js";
import { definirContagem, iniciarNavegacao } from "./js/navegacao.js";
import {
  abrirPainel,
  coletarPainel,
  fecharPainel,
  ligarPainel,
} from "./js/painelPosicao.js";
import { ligarPosicoes, renderPosicoes } from "./js/posicoes.js";
import { renderFatos, renderMacro, renderResumo, renderRiscos } from "./js/visaoGeral.js";

const AVISOS = [
  "CDB é estimado na curva com o CDI vigente; o Tesouro usa o preço de revenda do último pregão publicado pelo Tesouro Nacional. O extrato da instituição é a fonte oficial.",
  "P/VP, dividend yield, patrimônio e segmento são levantados por IA a partir de fontes públicas; confira antes de decidir.",
  "Este material é informativo e não constitui recomendação de investimento.",
];

const estado = { carteira: null, analise: null, historico: null };

/**
 * A régua única: o limite que o usuário configurou agora, não o que valia na
 * última execução — mudá-lo em Configurações move os traços na hora.
 */
const limiteConcentracao = () =>
  Number(
    estado.carteira?.config?.alerta_concentracao_pct ??
      estado.analise?.snapshot?.limite_concentracao_pct ??
      0
  );

// ── Desenho ────────────────────────────────

const acoesDaTabela = { editar: editarPosicao, excluir: excluirPosicao };

function renderAnalise() {
  const resultado = estado.analise;
  if (!resultado || resultado.vazio) {
    renderPosicoes(
      { posicoes: estado.carteira?.posicoes || [], limite: limiteConcentracao() },
      acoesDaTabela
    );
    renderEquivalencia(null);
    renderAnaliseVazia();
    return;
  }

  const { snapshot, ia, ia_erro: iaErro, fundamentos } = resultado;
  const herdadaDe = resultado.ia_reaproveitada_de || null;
  renderMacro(snapshot);
  renderEquivalencia(snapshot);
  renderResumo(snapshot, ia, fundamentos, herdadaDe);
  renderAlocacao(snapshot, fundamentos, limiteConcentracao());
  renderRiscos(snapshot, ia);
  renderFatos(ia);
  renderPosicoes(
    { posicoes: estado.carteira.posicoes, snapshot, fundamentos, limite: limiteConcentracao() },
    acoesDaTabela
  );
  renderFichas(fundamentos);
  renderLeitura(ia, iaErro, herdadaDe);
  renderAnaliseVazia();

  definirContagem("posicoes", snapshot.totais.posicoes);
  definirContagem("analise", fundamentos?.fichas?.length ?? "");
  definirContagem("visao-geral", snapshot.alertas.length || "");
}

async function abrirTela(id) {
  if (id !== "historico" || estado.historico) return;
  try {
    const { serie } = await api("/api/historico");
    estado.historico = serie;
    renderHistorico(serie);
    definirContagem("historico", serie.length || "");
  } catch (erro) {
    toast("Falha ao ler o histórico: " + erro.message, "erro");
  }
}

// ── Ações ──────────────────────────────────

function editarPosicao(id) {
  const posicao = estado.carteira.posicoes.find((p) => p.id === id);
  if (posicao) abrirPainel(posicao);
}

async function excluirPosicao(id) {
  const posicao = estado.carteira.posicoes.find((p) => p.id === id);
  const nome = posicao?.ticker || posicao?.banco || "esta posição";
  if (!confirm(`Excluir ${nome} da carteira?`)) return;
  try {
    await api(`/api/posicoes/${id}`, { method: "DELETE" });
    toast("Posição excluída.", "ok");
    await carregarCarteira();
  } catch (erro) {
    toast(erro.message, "erro");
  }
}

async function carregarCarteira() {
  estado.carteira = await api("/api/carteira");
  renderConfig(estado.carteira);
  estado.analise = await api("/api/analise");
  renderAnalise();
}

async function rodarAnalise(comIa) {
  const botao = comIa ? $("#btn-analise") : $("#btn-cotacoes");
  const original = botao.innerHTML;
  $$(".topo-acoes .btn").forEach((b) => (b.disabled = true));
  botao.innerHTML = `<span class="girando"></span>${comIa ? "Analisando…" : "Atualizando…"}`;
  if (comIa) toast("A análise consulta fontes na web e leva algum tempo.", "info", 9000);

  try {
    estado.analise = await api(`/api/analise?ia=${comIa ? 1 : 0}`, { method: "POST" });
    estado.historico = null;
    renderAnalise();
    await abrirTela(location.hash.replace("#", ""));
    if (comIa && estado.analise.ia_erro) toast(estado.analise.ia_erro, "erro", 9000);
    else toast(comIa ? "Análise concluída." : "Cotações atualizadas.", "ok");
  } catch (erro) {
    toast(erro.message, "erro", 9000);
  } finally {
    $$(".topo-acoes .btn").forEach((b) => (b.disabled = false));
    botao.innerHTML = original;
  }
}

async function salvarPosicao(evento) {
  evento.preventDefault();
  const id = $("#f-id").value;
  try {
    await api(id ? `/api/posicoes/${id}` : "/api/posicoes", {
      method: id ? "PUT" : "POST",
      body: JSON.stringify(coletarPainel()),
    });
    toast(id ? "Posição atualizada." : "Posição adicionada.", "ok");
    fecharPainel();
    await carregarCarteira();
  } catch (erro) {
    toast(erro.message, "erro", 7000);
  }
}

async function salvarConfig(evento) {
  evento.preventDefault();
  try {
    estado.carteira = await api("/api/config", {
      method: "POST",
      body: JSON.stringify(coletarConfig()),
    });
    renderAnalise();
    toast("Parâmetros salvos.", "ok");
  } catch (erro) {
    toast(erro.message, "erro");
  }
}

async function enviarAoTelegram() {
  try {
    await api("/api/telegram", { method: "POST" });
    toast("Relatório enviado ao Telegram.", "ok");
  } catch (erro) {
    toast(erro.message, "erro", 7000);
  }
}

/** Botões de IA e Telegram só ficam ativos quando o ambiente permite. */
async function aplicarStatus() {
  const status = await api("/api/status");
  $("#status-ia").textContent = status.ia_disponivel ? `IA: ${status.modelo}` : "IA indisponível";
  $("#status-ia").title = status.ia_motivo || "";
  $("#btn-analise").disabled = !status.ia_disponivel;
  $("#btn-telegram").disabled = !status.telegram_configurado;
  if (!status.telegram_configurado) {
    $("#btn-telegram").title = "Configure TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no .env";
  }
}

// ── Inicialização ──────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
  $("#rodape-aviso").innerHTML = AVISOS.join("<br>");
  $("#rodape-posicoes").textContent = AVISOS[0];
  $("#rodape-nav").textContent = "Roda só na sua máquina.";

  ligarPainel();
  ligarPosicoes();
  ligarEquivalencia();
  iniciarNavegacao(abrirTela);

  $("#btn-nova").addEventListener("click", () => abrirPainel());
  $("#btn-analise").addEventListener("click", () => rodarAnalise(true));
  $("#btn-cotacoes").addEventListener("click", () => rodarAnalise(false));
  $("#btn-telegram").addEventListener("click", enviarAoTelegram);
  $("#form-posicao").addEventListener("submit", salvarPosicao);
  $("#form-config").addEventListener("submit", salvarConfig);

  try {
    await aplicarStatus();
    await carregarCarteira();
  } catch (erro) {
    toast("Falha ao carregar: " + erro.message, "erro", 9000);
  }
});

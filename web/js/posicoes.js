/** Tabela de posições e painel lateral de cadastro. */

import { $, $$, classeSinal, dataBR, esc, moeda, num, pct } from "./formato.js";
import { icone } from "./icones.js";

const ROTULO_TIPO = { fii: "FII", acao: "AÇÃO", cdb: "CDB" };

const ROTULO_TAXA = {
  CDI: "Taxa (% do CDI)",
  PRE: "Taxa (% a.a.)",
  IPCA: "Spread sobre IPCA (% a.a.)",
};

const indexar = (itens, chave) =>
  Object.fromEntries((itens || []).map((item) => [item[chave], item]));

/** Cupons já pagos e a data do próximo, num CDB de juros mensais. */
function detalheJurosMensais(calculada) {
  const proximo = calculada.proximo_pagamento
    ? `próximo em ${dataBR(calculada.proximo_pagamento)}`
    : "sem novos pagamentos";
  return `juros mensais · ${moeda(calculada.juros_recebidos_liquido)} recebidos · ${proximo}`;
}

function detalheCdb(posicao, calculada) {
  const mensal = posicao.pagamento_juros === "mensal";
  if (!calculada) {
    return `vence ${dataBR(posicao.data_vencimento)}${mensal ? " · juros mensais" : ""}`;
  }
  const situacao = calculada.vencido
    ? '<strong class="neg">vencido</strong>'
    : `vence em ${calculada.dias_para_vencer} dias`;
  const prazo = `${dataBR(posicao.data_vencimento)} · ${situacao} · líquido ${moeda(calculada.valor_liquido)}`;
  return mensal ? `${prazo}<br>${detalheJurosMensais(calculada)}` : prazo;
}

function detalheVariavel(posicao, calculada) {
  if (calculada?.preco_atual) {
    return `${posicao.quantidade} × ${moeda(calculada.preco_atual)} · PM ${moeda(posicao.preco_medio)}`;
  }
  return `${posicao.quantidade} cotas · PM ${moeda(posicao.preco_medio)}`;
}

function celulaResultado(calculada) {
  if (!calculada) return "—";
  const sinal = classeSinal(calculada.resultado);
  return `<span class="${sinal}">${moeda(calculada.resultado)}
    <div class="apoio ${sinal}">${pct(calculada.resultado_pct)}</div></span>`;
}

function linha(posicao, calculada, ficha) {
  const ehCdb = posicao.tipo === "cdb";
  const nome = ehCdb ? posicao.banco : posicao.ticker;
  const detalhe = ehCdb ? detalheCdb(posicao, calculada) : detalheVariavel(posicao, calculada);
  const segmento = ehCdb
    ? esc(posicao.nome?.replace(`CDB ${posicao.banco} `, "") || "CDB")
    : esc(ficha?.segmento || "—");

  return `<tr>
    <td><span class="etiqueta etiqueta-${posicao.tipo}">${ROTULO_TIPO[posicao.tipo]}</span></td>
    <td>
      <strong>${esc(nome)}</strong>
      ${ficha?.nome ? `<div class="apoio">${esc(ficha.nome)}</div>` : ""}
      <div class="apoio">${detalhe}</div>
      ${posicao.observacao ? `<div class="apoio">${esc(posicao.observacao)}</div>` : ""}
      ${calculada?.erro_cotacao ? '<div class="apoio neg">cotação indisponível</div>' : ""}
    </td>
    <td>${segmento}${ficha?.gestora ? `<div class="apoio">${esc(ficha.gestora)}</div>` : ""}</td>
    <td class="num mono">${ficha?.p_vp ? num(ficha.p_vp, 2) : "—"}</td>
    <td class="num mono">${ficha?.dy_12m_pct ? pct(ficha.dy_12m_pct, 1, false) : "—"}</td>
    <td class="num mono">${calculada ? moeda(calculada.valor_atual) : "—"}</td>
    <td class="num mono">${celulaResultado(calculada)}</td>
    <td class="num mono">${calculada ? pct(calculada.peso_pct, 1, false) : "—"}</td>
    <td class="num">
      <button class="btn-icone" data-editar="${posicao.id}" title="Editar" aria-label="Editar ${esc(nome)}">${icone("editar", 16)}</button>
      <button class="btn-icone perigo" data-excluir="${posicao.id}" title="Excluir" aria-label="Excluir ${esc(nome)}">${icone("excluir", 16)}</button>
    </td>
  </tr>`;
}

/**
 * Desenha a tabela.
 *
 * @param {object[]} posicoes Cadastro, vindo de /api/carteira.
 * @param {object|null} snapshot Cálculo, para valores e pesos.
 * @param {object|null} fundamentos Fichas da IA, para segmento e indicadores.
 * @param {{editar: Function, excluir: Function}} acoes
 */
export function renderPosicoes(posicoes, snapshot, fundamentos, acoes) {
  if (!posicoes.length) {
    $("#posicoes").innerHTML =
      '<div class="vazio">Nenhuma posição cadastrada. Clique em “+ Nova posição”.</div>';
    return;
  }

  const calculadas = indexar(snapshot?.posicoes, "id");
  const fichas = indexar(fundamentos?.fichas, "ticker");

  $("#posicoes").innerHTML = `
    <div class="tabela-rolagem">
      <table class="tabela">
        <thead><tr>
          <th>Tipo</th><th>Ativo</th><th>Segmento</th>
          <th class="num">P/VP</th><th class="num">DY 12M</th>
          <th class="num">Valor</th><th class="num">Resultado</th><th class="num">Peso</th><th></th>
        </tr></thead>
        <tbody>${posicoes
          .map((p) => linha(p, calculadas[p.id], fichas[p.ticker]))
          .join("")}</tbody>
      </table>
    </div>`;

  $$("[data-editar]").forEach((b) =>
    b.addEventListener("click", () => acoes.editar(b.dataset.editar))
  );
  $$("[data-excluir]").forEach((b) =>
    b.addEventListener("click", () => acoes.excluir(b.dataset.excluir))
  );
}

// ── Painel de cadastro ─────────────────────

const tipoSelecionado = () => $('#seletor-tipo [aria-pressed="true"]').dataset.tipo;

function selecionarTipo(tipo) {
  $$("#seletor-tipo button").forEach((b) =>
    b.setAttribute("aria-pressed", String(b.dataset.tipo === tipo))
  );
  const ehCdb = tipo === "cdb";
  $$(".campo-rv").forEach((el) => el.classList.toggle("hidden", ehCdb));
  $$(".campo-rf").forEach((el) => el.classList.toggle("hidden", !ehCdb));
  $("#f-taxa-label").textContent = ROTULO_TAXA[$("#f-indexador").value];
}

function preencherCampos(posicao) {
  $("#f-observacao").value = posicao.observacao || "";
  if (posicao.tipo === "cdb") {
    $("#f-banco").value = posicao.banco || "";
    $("#f-valor-inicial").value = posicao.valor_inicial ?? "";
    $("#f-indexador").value = posicao.indexador || "CDI";
    $("#f-taxa").value = posicao.taxa ?? "";
    $("#f-data-aplicacao").value = posicao.data_aplicacao || "";
    $("#f-data-vencimento").value = posicao.data_vencimento || "";
    $("#f-pagamento-juros").value = posicao.pagamento_juros || "vencimento";
    $("#f-liquidez").checked = !!posicao.liquidez_diaria;
    return;
  }
  $("#f-ticker").value = posicao.ticker || "";
  $("#f-quantidade").value = posicao.quantidade ?? "";
  $("#f-preco-medio").value = posicao.preco_medio ?? "";
  $("#f-data-compra").value = posicao.data_compra || "";
}

/** Abre o painel; sem argumento, para cadastrar uma posição nova. */
export function abrirPainel(posicao = null) {
  $("#form-posicao").reset();
  $("#f-id").value = posicao?.id || "";
  $("#painel-titulo").textContent = posicao ? "Editar posição" : "Nova posição";
  if (posicao) preencherCampos(posicao);
  selecionarTipo(posicao?.tipo || "fii");

  $("#veu").classList.remove("hidden");
  $("#painel").classList.remove("hidden");
  ($("#f-ticker").offsetParent ? $("#f-ticker") : $("#f-banco")).focus();
}

export function fecharPainel() {
  $("#veu").classList.add("hidden");
  $("#painel").classList.add("hidden");
  $("#form-posicao").reset();
  $("#f-id").value = "";
}

export const painelAberto = () => !$("#painel").classList.contains("hidden");

/** Lê o formulário no formato que a API espera. */
export function coletarPainel() {
  const tipo = tipoSelecionado();
  const base = { tipo, observacao: $("#f-observacao").value };

  if (tipo === "cdb") {
    return {
      ...base,
      banco: $("#f-banco").value,
      valor_inicial: $("#f-valor-inicial").value,
      indexador: $("#f-indexador").value,
      taxa: $("#f-taxa").value,
      data_aplicacao: $("#f-data-aplicacao").value,
      data_vencimento: $("#f-data-vencimento").value,
      pagamento_juros: $("#f-pagamento-juros").value,
      liquidez_diaria: $("#f-liquidez").checked,
    };
  }
  return {
    ...base,
    ticker: $("#f-ticker").value,
    quantidade: $("#f-quantidade").value,
    preco_medio: $("#f-preco-medio").value,
    data_compra: $("#f-data-compra").value,
  };
}

/** Liga os controles do painel que não dependem de dados. */
export function ligarPainel() {
  $$("#seletor-tipo button").forEach((b) =>
    b.addEventListener("click", () => selecionarTipo(b.dataset.tipo))
  );
  $("#f-indexador").addEventListener("change", () => {
    $("#f-taxa-label").textContent = ROTULO_TAXA[$("#f-indexador").value];
  });
  $("#btn-cancelar").addEventListener("click", fecharPainel);
  $("#btn-fechar-painel").addEventListener("click", fecharPainel);
  $("#veu").addEventListener("click", fecharPainel);
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && painelAberto()) fecharPainel();
  });
}

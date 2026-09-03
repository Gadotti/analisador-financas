/** Tabela de posições e painel lateral de cadastro. */

import { $, $$, classeSinal, dataBR, esc, moeda, num, pct } from "./formato.js";
import { icone } from "./icones.js";

const ROTULO_TIPO = { fii: "FII", acao: "AÇÃO", cdb: "CDB", tesouro: "TESOURO" };

const ROTULO_TAXA = {
  CDI: "Taxa (% do CDI)",
  SELIC: "Ágio sobre a Selic (% a.a.)",
  PRE: "Taxa (% a.a.)",
  IPCA: "Spread sobre IPCA (% a.a.)",
};

const CUPOM_ROTULO = { mensal: "juros mensais", semestral: "juros semestrais" };

/**
 * O que muda entre um CDB e um título do Tesouro no formulário: o indexador
 * disponível e a periodicidade do cupom. O resto dos campos é comum aos dois.
 */
const FORMULARIO_RF = {
  cdb: {
    indexadores: [["CDI", "% do CDI"], ["PRE", "Prefixado (% a.a.)"], ["IPCA", "IPCA + (% a.a.)"]],
    pagamentos: [["vencimento", "No vencimento"], ["mensal", "Mensal"]],
  },
  tesouro: {
    indexadores: [["SELIC", "Selic + (% a.a.)"], ["PRE", "Prefixado (% a.a.)"], ["IPCA", "IPCA + (% a.a.)"]],
    pagamentos: [["vencimento", "No vencimento"], ["semestral", "Semestral"]],
  },
};

const ehRendaFixa = (tipo) => tipo in FORMULARIO_RF;

const indexar = (itens, chave) =>
  Object.fromEntries((itens || []).map((item) => [item[chave], item]));

/** Cupons já pagos e a data do próximo, num título que paga juros no caminho. */
function detalheCupons(posicao, calculada) {
  const proximo = calculada.proximo_pagamento
    ? `próximo em ${dataBR(calculada.proximo_pagamento)}`
    : "sem novos pagamentos";
  const rotulo = CUPOM_ROTULO[posicao.pagamento_juros];
  return `${rotulo} · ${moeda(calculada.juros_recebidos_liquido)} recebidos · ${proximo}`;
}

function detalheRendaFixa(posicao, calculada) {
  const cupom = CUPOM_ROTULO[posicao.pagamento_juros];
  if (!calculada) {
    return `vence ${dataBR(posicao.data_vencimento)}${cupom ? ` · ${cupom}` : ""}`;
  }
  const situacao = calculada.vencido
    ? '<strong class="neg">vencido</strong>'
    : `vence em ${calculada.dias_para_vencer} dias`;
  const prazo = `${dataBR(posicao.data_vencimento)} · ${situacao} · líquido ${moeda(calculada.valor_liquido)}`;
  return cupom ? `${prazo}<br>${detalheCupons(posicao, calculada)}` : prazo;
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

/** Coluna "Ativo": o banco identifica o CDB; o Tesouro, o nome do papel. */
const nomeDaLinha = (posicao) =>
  ({ cdb: posicao.banco, tesouro: posicao.nome })[posicao.tipo] || posicao.ticker;

/** Coluna "Segmento": a remuneração, na renda fixa; o setor, na renda variável. */
function segmentoDaLinha(posicao, calculada, ficha) {
  if (!ehRendaFixa(posicao.tipo)) return esc(ficha?.segmento || "—");
  return esc(calculada?.rotulo_taxa || ROTULO_TIPO[posicao.tipo]);
}

function linha(posicao, calculada, ficha) {
  const rendaFixa = ehRendaFixa(posicao.tipo);
  const nome = nomeDaLinha(posicao);
  const detalhe = rendaFixa
    ? detalheRendaFixa(posicao, calculada)
    : detalheVariavel(posicao, calculada);
  const segmento = segmentoDaLinha(posicao, calculada, ficha);

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

/** Repovoa um select preservando o valor escolhido, quando ele ainda existe. */
function preencherSelect(seletor, opcoes) {
  const anterior = $(seletor).value;
  $(seletor).innerHTML = opcoes
    .map(([valor, rotulo]) => `<option value="${valor}">${rotulo}</option>`)
    .join("");
  if (opcoes.some(([valor]) => valor === anterior)) $(seletor).value = anterior;
}

function selecionarTipo(tipo) {
  $$("#seletor-tipo button").forEach((b) =>
    b.setAttribute("aria-pressed", String(b.dataset.tipo === tipo))
  );
  const rendaFixa = ehRendaFixa(tipo);
  $$(".campo-rv").forEach((el) => el.classList.toggle("hidden", rendaFixa));
  $$(".campo-rf").forEach((el) => el.classList.toggle("hidden", !rendaFixa));
  $$(".campo-cdb").forEach((el) => el.classList.toggle("hidden", tipo !== "cdb"));
  $$(".campo-tesouro").forEach((el) => el.classList.toggle("hidden", tipo !== "tesouro"));

  if (rendaFixa) {
    preencherSelect("#f-indexador", FORMULARIO_RF[tipo].indexadores);
    preencherSelect("#f-pagamento-juros", FORMULARIO_RF[tipo].pagamentos);
  }
  atualizarRotuloTaxa();
}

const atualizarRotuloTaxa = () => {
  $("#f-taxa-label").textContent = ROTULO_TAXA[$("#f-indexador").value] || "Taxa";
};

function preencherRendaFixa(posicao) {
  $("#f-banco").value = posicao.banco || "";
  $("#f-nome-tesouro").value = posicao.tipo === "tesouro" ? posicao.nome || "" : "";
  $("#f-valor-inicial").value = posicao.valor_inicial ?? "";
  $("#f-indexador").value = posicao.indexador || $("#f-indexador").value;
  $("#f-taxa").value = posicao.taxa ?? "";
  $("#f-data-aplicacao").value = posicao.data_aplicacao || "";
  $("#f-data-vencimento").value = posicao.data_vencimento || "";
  $("#f-pagamento-juros").value = posicao.pagamento_juros || "vencimento";
  $("#f-liquidez").checked = !!posicao.liquidez_diaria;
}

function preencherCampos(posicao) {
  $("#f-observacao").value = posicao.observacao || "";
  if (ehRendaFixa(posicao.tipo)) {
    preencherRendaFixa(posicao);
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
  // O tipo primeiro: é ele que monta as opções de indexador e de cupom.
  selecionarTipo(posicao?.tipo || "fii");
  if (posicao) preencherCampos(posicao);

  $("#veu").classList.remove("hidden");
  $("#painel").classList.remove("hidden");
  primeiroCampoVisivel()?.focus();
}

/** Primeiro campo que o tipo escolhido deixou visível — onde o cursor entra. */
const primeiroCampoVisivel = () =>
  $$("#form-posicao input, #form-posicao select").find((el) => el.offsetParent);

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

  if (ehRendaFixa(tipo)) {
    return {
      ...base,
      banco: tipo === "cdb" ? $("#f-banco").value : "",
      nome: tipo === "tesouro" ? $("#f-nome-tesouro").value : "",
      valor_inicial: $("#f-valor-inicial").value,
      indexador: $("#f-indexador").value,
      taxa: $("#f-taxa").value,
      data_aplicacao: $("#f-data-aplicacao").value,
      data_vencimento: $("#f-data-vencimento").value,
      pagamento_juros: $("#f-pagamento-juros").value,
      liquidez_diaria: tipo === "cdb" && $("#f-liquidez").checked,
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
  $("#f-indexador").addEventListener("change", atualizarRotuloTaxa);
  $("#btn-cancelar").addEventListener("click", fecharPainel);
  $("#btn-fechar-painel").addEventListener("click", fecharPainel);
  $("#veu").addEventListener("click", fecharPainel);
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && painelAberto()) fecharPainel();
  });
}

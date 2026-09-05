/** Painel lateral de cadastro e edição de uma posição. */

import { $, $$ } from "./formato.js";

const ROTULO_TAXA = {
  CDI: "Taxa (% do CDI)",
  SELIC: "Ágio sobre a Selic (% a.a.)",
  PRE: "Taxa (% a.a.)",
  IPCA: "Spread sobre IPCA (% a.a.)",
};

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
    // A taxa do título público sai do pregão da compra; digitá-la é opcional.
    taxaOpcional: true,
  },
};

const ehRendaFixa = (tipo) => tipo in FORMULARIO_RF;

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
  atualizarRotuloTaxa(tipo);
}

const atualizarRotuloTaxa = (tipo) => {
  const opcional = FORMULARIO_RF[tipo]?.taxaOpcional;
  const base = ROTULO_TAXA[$("#f-indexador").value] || "Taxa";
  $("#f-taxa-label").textContent = opcional ? `${base} — opcional` : base;
  $("#f-taxa-dica").classList.toggle("hidden", !opcional);
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
  $("#f-indexador").addEventListener("change", () => atualizarRotuloTaxa(tipoSelecionado()));
  $("#btn-cancelar").addEventListener("click", fecharPainel);
  $("#btn-fechar-painel").addEventListener("click", fecharPainel);
  $("#veu").addEventListener("click", fecharPainel);
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && painelAberto()) fecharPainel();
  });
}

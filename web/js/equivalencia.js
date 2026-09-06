/**
 * Conversor entre renda fixa isenta (LCI, LCA) e tributada (CDB).
 *
 * Uma LCI é ofertada em taxa líquida, um CDB em taxa bruta: comparar as duas
 * exige trazer uma para a régua da outra, e a régua é a alíquota do IR, que cai
 * com o prazo. As alíquotas não são escritas aqui — chegam em
 * `snapshot.ir_renda_fixa`, calculadas por `analise.fixed_income`, para que
 * exista uma tabela de IR só no sistema. O que este módulo faz é converter a
 * taxa que o usuário digita; não é número da carteira, e por isso não passa
 * pelo Python.
 */

import { $, $$, esc, mostrar, num } from "./formato.js";
import { icone } from "./icones.js";

/** Os dois lados da conversão, com os papéis que caem em cada um. */
const ISENTO = { titulo: "Isento de IR", exemplos: "LCI · LCA · CRI · CRA · LIG" };
const TRIBUTADO = { titulo: "Tributado — IR na fonte", exemplos: "CDB · RDB · LC · Tesouro" };

// Quem entra e quem sai fica escrito em cima de cada painel: a seta do botão
// sozinha não diz qual dos dois lados é o que o banco ofereceu.
const PAPEL_ENTRADA = "Taxa ofertada";
const PAPEL_SAIDA = "Equivale a";

/**
 * `converter` leva a taxa anual digitada até o outro lado. Tirar o IR é
 * multiplicar pelo que sobra; devolvê-lo é dividir pelo mesmo fator.
 */
const SENTIDOS = {
  isento: { de: ISENTO, para: TRIBUTADO, converter: (anual, sobra) => anual / sobra },
  tributado: { de: TRIBUTADO, para: ISENTO, converter: (anual, sobra) => anual * sobra },
};

// Prazo escolhido por padrão: 1 a 2 anos, o intervalo em que a maioria das LCIs
// é ofertada. É só o ponto de partida — a escolha é do usuário.
const FAIXA_PADRAO = 2;

const estado = { sentido: "isento", faixa: FAIXA_PADRAO, cdi: null, faixas: [] };

const unidade = () => $("#equivalencia-unidade").value;
const emCdi = (anual) => (estado.cdi ? (anual / estado.cdi) * 100 : null);

const comoCdi = (anual) => {
  const relativa = emCdi(anual);
  return relativa == null ? "—" : `${num(relativa, 1)}% do CDI`;
};

const comoAoAno = (anual) => `${num(anual)}% a.a.`;

/** Aceita vírgula: o usuário digita a taxa como a corretora a escreve. */
function taxaDigitada() {
  const valor = Number.parseFloat($("#equivalencia-taxa").value.replace(",", "."));
  return Number.isFinite(valor) && valor > 0 ? valor : null;
}

/** Taxa digitada em % a.a. — `null` quando falta o CDI para converter. */
function emAnual(taxa) {
  if (taxa == null) return null;
  if (unidade() !== "cdi") return taxa;
  return estado.cdi ? (taxa / 100) * estado.cdi : null;
}

/**
 * As duas unidades, com a do campo na frente: quem digita em % do CDI lê a
 * resposta em % do CDI, e o prefixado equivalente logo abaixo.
 */
const nasDuasUnidades = (anual) =>
  unidade() === "cdi" ? [comoCdi(anual), comoAoAno(anual)] : [comoAoAno(anual), comoCdi(anual)];

const preencher = (atributo, texto) =>
  $$(`[${atributo}]`).forEach((el) => (el.textContent = texto));

// ─────────────────────────────────────────────
// Desenho
// ─────────────────────────────────────────────

/** Os quatro cartões de prazo. Montados uma vez: clicá-los não os redesenha. */
function montarFaixas() {
  $("#equivalencia-faixas").innerHTML = estado.faixas
    .map(
      (faixa, i) => `<button type="button" class="faixa" data-faixa="${i}">
        <span class="faixa-prazo">${esc(faixa.rotulo)}</span>
        <span class="faixa-ir">IR de ${num(faixa.aliquota_pct, 1)}%</span>
        <span class="faixa-valor mono" data-faixa-principal>—</span>
        <span class="faixa-apoio mono" data-faixa-secundario></span>
      </button>`
    )
    .join("");
}

function pintarFaixas(anual, converter) {
  $$("#equivalencia-faixas .faixa").forEach((botao, i) => {
    botao.setAttribute("aria-pressed", String(i === estado.faixa));
    const [principal, secundario] =
      anual == null ? ["—", ""] : nasDuasUnidades(converter(anual, sobraDoIr(i)));
    botao.querySelector("[data-faixa-principal]").textContent = principal;
    botao.querySelector("[data-faixa-secundario]").textContent = secundario;
  });
}

/** Fração do rendimento que escapa do IR na faixa de índice `i`. */
const sobraDoIr = (i) => 1 - estado.faixas[i].aliquota_pct / 100;

function pintarConversor(anual, sentido) {
  const faixa = estado.faixas[estado.faixa];
  const [principal, secundario] =
    anual == null ? ["—", ""] : nasDuasUnidades(sentido.converter(anual, sobraDoIr(estado.faixa)));

  preencher("data-para-principal", principal);
  preencher("data-para-secundario", secundario);
  preencher(
    "data-para-apoio",
    anual == null ? "" : `${faixa.rotulo} · IR de ${num(faixa.aliquota_pct, 1)}%`
  );
}

function desenhar() {
  const sentido = SENTIDOS[estado.sentido];
  preencher("data-de-papel", PAPEL_ENTRADA);
  preencher("data-de-titulo", sentido.de.titulo);
  preencher("data-de-exemplos", sentido.de.exemplos);
  preencher("data-para-papel", PAPEL_SAIDA);
  preencher("data-para-titulo", sentido.para.titulo);
  preencher("data-para-exemplos", sentido.para.exemplos);

  const anual = emAnual(taxaDigitada());
  preencher("data-de-apoio", anual == null ? avisoDaEntrada() : `= ${nasDuasUnidades(anual)[1]}`);
  pintarConversor(anual, sentido);
  pintarFaixas(anual, sentido.converter);
}

const avisoDaEntrada = () =>
  taxaDigitada() != null && !estado.cdi
    ? "Sem o CDI do dia não dá para converter % do CDI."
    : "Informe a taxa ofertada.";

/**
 * @param {object|null} snapshot Sem análise em disco não há CDI nem tabela de
 *   IR — o cartão explica o que fazer em vez de mostrar contas vazias.
 */
export function renderEquivalencia(snapshot) {
  estado.faixas = snapshot?.ir_renda_fixa || [];
  estado.cdi = snapshot?.macro?.cdi_anual_pct?.valor ?? null;

  const pronto = estado.faixas.length > 0;
  mostrar("#equivalencia-corpo", pronto);
  mostrar("#equivalencia-vazio", !pronto);
  if (!pronto) return;

  estado.faixa = Math.min(FAIXA_PADRAO, estado.faixas.length - 1);
  $("#equivalencia-base").textContent = estado.cdi
    ? `CDI de referência ${num(estado.cdi)}% a.a.`
    : "CDI do dia indisponível";
  montarFaixas();
  desenhar();
}

// ─────────────────────────────────────────────
// Interação
// ─────────────────────────────────────────────

function escolherFaixa(evento) {
  const botao = evento.target.closest("[data-faixa]");
  if (!botao) return;
  estado.faixa = Number(botao.dataset.faixa);
  desenhar();
}

function inverterSentido() {
  estado.sentido = estado.sentido === "isento" ? "tributado" : "isento";
  desenhar();
}

export function ligarEquivalencia() {
  $("#equivalencia-trocar").innerHTML = icone("trocar", 18);
  $("#equivalencia-trocar").addEventListener("click", inverterSentido);
  $("#equivalencia-faixas").addEventListener("click", escolherFaixa);
  $("#equivalencia-taxa").addEventListener("input", desenhar);
  $("#equivalencia-unidade").addEventListener("change", desenhar);
}

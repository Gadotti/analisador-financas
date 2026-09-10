/**
 * web/js/painelPosicao.js — o formulário de cadastro de uma posição.
 *
 * Sem framework de DOM (não há jsdom no projeto): um `document` mínimo que
 * inventa um elemento para cada seletor pedido, no mesmo espírito de
 * `configuracoes.test.js`.
 *
 * O que estes testes travam é o contrato entre as duas metades do cadastro: o
 * painel declara numa tabela o indexador e o cupom de cada tipo de renda fixa,
 * e `rendaFixa.REGRAS` os valida noutra. Uma opção oferecida na tela que o
 * núcleo recusa vira erro de validação na cara do usuário; um tipo novo que o
 * coletor não conhece grava a posição sem o campo que só ele tem.
 */

import * as portfolio from "../../src/core/portfolio.js";

/** Um elemento da tela, com o mínimo de DOM que o módulo usa. */
function elemento(extras = {}) {
  const el = {
    value: "",
    checked: false,
    innerHTML: "",
    textContent: "",
    classes: new Set(),
    dataset: {},
    atributos: {},
    // Qualquer campo conta como visível: quem decide o que aparece é a classe
    // "hidden", e é ela que os testes leem.
    offsetParent: {},
    ...extras,
  };
  // O módulo sempre passa o segundo argumento, então `toggle` aqui é só um
  // "liga/desliga" explícito — não o alternador do DOM real.
  el.classList = {
    add: (classe) => el.classes.add(classe),
    remove: (classe) => el.classes.delete(classe),
    contains: (classe) => el.classes.has(classe),
    toggle: (classe, ligado) =>
      ligado ? el.classes.add(classe) : el.classes.delete(classe),
  };
  el.setAttribute = (nome, valor) => {
    el.atributos[nome] = valor;
  };
  el.addEventListener = () => {};
  el.focus = () => {};
  el.reset = () => {};
  return el;
}

const TIPOS = ["fii", "acao", "cdb", "lci", "lca", "tesouro"];

/** Campos que só alguns tipos usam — `data-campo` no HTML. */
const OPCIONAIS = ["banco", "nome", "liquidez"];

let tela;
let botoes;
let opcionais;
let painel;

beforeAll(async () => {
  botoes = TIPOS.map((tipo) => elemento({ dataset: { tipo } }));
  opcionais = Object.fromEntries(OPCIONAIS.map((campo) => [campo, elemento()]));
  tela = {};

  const listas = {
    "#seletor-tipo button": botoes,
    ...Object.fromEntries(
      OPCIONAIS.map((campo) => [`[data-campo="${campo}"]`, [opcionais[campo]]]),
    ),
  };

  global.document = {
    querySelector(seletor) {
      if (seletor === '#seletor-tipo [aria-pressed="true"]') {
        return botoes.find((b) => b.atributos["aria-pressed"] === "true");
      }
      tela[seletor] = tela[seletor] ?? elemento();
      return tela[seletor];
    },
    querySelectorAll: (seletor) => listas[seletor] ?? [],
    addEventListener: () => {},
  };
  painel = await import("../../web/js/painelPosicao.js");
});

afterAll(() => {
  delete global.document;
});

/** Os `value` das <option> que o painel escreveu num select. */
const opcoesDe = (seletor) =>
  [...tela[seletor].innerHTML.matchAll(/value="([^"]+)"/g)].map(([, valor]) => valor);

const visivel = (campo) => !opcionais[campo].classes.has("hidden");

const TITULO = {
  valor_inicial: "5000",
  taxa: "95",
  data_aplicacao: "2025-01-02",
  data_vencimento: "2027-01-04",
};

/** Abre o painel num tipo e preenche os campos comuns da renda fixa. */
function preencher(tipo, extras = {}) {
  painel.abrirPainel({ tipo });
  const campos = { ...TITULO, ...extras };
  for (const [campo, valor] of Object.entries(campos)) {
    document.querySelector(`#f-${campo.replaceAll("_", "-")}`).value = valor;
  }
  return painel.coletarPainel();
}

// ─────────────────────────────────────────────
// Contrato com rendaFixa.REGRAS
// ─────────────────────────────────────────────

const INDEXADORES = {
  cdb: portfolio.INDEXADORES_BANCARIO,
  lci: portfolio.INDEXADORES_BANCARIO,
  lca: portfolio.INDEXADORES_BANCARIO,
  tesouro: portfolio.INDEXADORES_TESOURO,
};

const PAGAMENTOS = {
  cdb: portfolio.PAGAMENTOS_CDB,
  lci: portfolio.PAGAMENTOS_LETRA,
  lca: portfolio.PAGAMENTOS_LETRA,
  tesouro: portfolio.PAGAMENTOS_TESOURO,
};

describe.each(portfolio.TIPOS_RENDA_FIXA)("painel de %s", (tipo) => {
  test("oferece exatamente os indexadores e os cupons que o cadastro aceita", () => {
    painel.abrirPainel({ tipo });

    expect(opcoesDe("#f-indexador")).toEqual(INDEXADORES[tipo]);
    expect(opcoesDe("#f-pagamento-juros")).toEqual(PAGAMENTOS[tipo]);
  });

  test("o que o formulário coleta é uma posição válida", () => {
    const coletado = preencher(tipo, { banco: "Sofisa" });
    const posicao = portfolio.normalizar(coletado);

    expect(posicao.tipo).toBe(tipo);
    expect(posicao.valor_inicial).toBe(5000);
    expect(posicao.data_vencimento).toBe("2027-01-04");
    expect(posicao.nome).toBeTruthy();
  });
});

// ─────────────────────────────────────────────
// Campos de cada tipo
// ─────────────────────────────────────────────

test("o papel bancário pede o banco emissor; o Tesouro, não", () => {
  for (const tipo of portfolio.TIPOS_BANCARIOS) {
    painel.abrirPainel({ tipo });
    expect(visivel("banco")).toBe(true);
    expect(preencher(tipo, { banco: "Sofisa" }).banco).toBe("Sofisa");
  }

  painel.abrirPainel({ tipo: "tesouro" });
  expect(visivel("banco")).toBe(false);
  expect(preencher("tesouro", { banco: "Sofisa" }).banco).toBe("");
});

test("só o CDB oferece a caixa de liquidez diária", () => {
  painel.abrirPainel({ tipo: "cdb" });
  expect(visivel("liquidez")).toBe(true);

  for (const tipo of ["lci", "lca", "tesouro"]) {
    painel.abrirPainel({ tipo });
    expect(visivel("liquidez")).toBe(false);
    document.querySelector("#f-liquidez").checked = true;
    expect(painel.coletarPainel().liquidez_diaria).toBe(false);
  }
});

test("só o Tesouro tem nome próprio no cadastro", () => {
  painel.abrirPainel({ tipo: "tesouro" });
  expect(visivel("nome")).toBe(true);

  painel.abrirPainel({ tipo: "lci" });
  expect(visivel("nome")).toBe(false);
  document.querySelector("#f-nome-titulo").value = "LCI antiga";
  expect(painel.coletarPainel().nome).toBe("");
});

test("a dica da taxa explica a isenção da letra e a busca do Tesouro", () => {
  painel.abrirPainel({ tipo: "lci" });
  expect(tela["#f-taxa-dica"].textContent).toMatch(/[Ii]senta de IR/);
  expect(tela["#f-taxa-dica"].classes.has("hidden")).toBe(false);

  painel.abrirPainel({ tipo: "tesouro" });
  expect(tela["#f-taxa-dica"].textContent).toMatch(/pregão da compra/);
  expect(tela["#f-taxa-label"].textContent).toMatch(/opcional/);

  painel.abrirPainel({ tipo: "cdb" });
  expect(tela["#f-taxa-dica"].textContent).toBe("");
  expect(tela["#f-taxa-dica"].classes.has("hidden")).toBe(true);
  expect(tela["#f-taxa-label"].textContent).not.toMatch(/opcional/);
});

test("a renda variável esconde os campos de renda fixa, e o contrário também", () => {
  const rv = [];
  const rf = [];
  global.document.querySelectorAll = (seletor) => {
    if (seletor === ".campo-rv") return rv;
    if (seletor === ".campo-rf") return rf;
    if (seletor === "#seletor-tipo button") return botoes;
    const campo = seletor.match(/^\[data-campo="(\w+)"\]$/);
    return campo ? [opcionais[campo[1]]] : [];
  };
  rv.push(elemento());
  rf.push(elemento());

  painel.abrirPainel({ tipo: "fii" });
  expect(rv[0].classes.has("hidden")).toBe(false);
  expect(rf[0].classes.has("hidden")).toBe(true);

  painel.abrirPainel({ tipo: "lca" });
  expect(rv[0].classes.has("hidden")).toBe(true);
  expect(rf[0].classes.has("hidden")).toBe(false);
});

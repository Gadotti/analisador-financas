/**
 * web/js/estadoVisual.js e web/js/avisoAnalise.js — o que uma atualização em
 * segundo plano não pode apagar, e o aviso quando ela não pôde acontecer.
 *
 * Sem jsdom (mesmo critério dos demais testes de web/js/): um `document` mínimo
 * com o que os módulos usam.
 */

import { jest } from "@jest/globals";

function dobra(rotulo, aberta = false) {
  return { open: aberta, querySelector: () => ({ textContent: `  ${rotulo}\n` }) };
}

function elemento() {
  const classes = new Set(["hidden"]);
  return {
    textContent: "",
    classList: {
      add: (c) => classes.add(c),
      remove: (c) => classes.delete(c),
      contains: (c) => classes.has(c),
    },
  };
}

let preservandoDobras;
let digitandoEmCampo;
let horaDaAtualizacao;
let renderAvisoAnalise;
let dobras;
let pilula;

beforeAll(async () => {
  ({ preservandoDobras, digitandoEmCampo } = await import("../../web/js/estadoVisual.js"));
  ({ horaDaAtualizacao, renderAvisoAnalise } = await import("../../web/js/avisoAnalise.js"));
});

beforeEach(() => {
  dobras = [];
  pilula = elemento();
  global.document = {
    querySelectorAll: (seletor) =>
      seletor === "details[open]" ? dobras.filter((d) => d.open) : dobras,
    querySelector: (seletor) => (seletor === "#pilula-analise" ? pilula : null),
  };
});

afterEach(() => {
  delete global.document;
});

describe("preservandoDobras", () => {
  test("reabre as dobras que estavam abertas depois de o redesenho as recriar fechadas", () => {
    dobras = [dobra("Contexto de mercado", true), dobra("Alerta de FGC"), dobra("Outro", true)];

    preservandoDobras(() => {
      dobras = [dobra("Contexto de mercado"), dobra("Alerta de FGC"), dobra("Outro")];
    });

    expect(dobras.map((d) => d.open)).toEqual([true, false, true]);
  });

  test("não abre nada quando nada estava aberto", () => {
    dobras = [dobra("A"), dobra("B")];
    preservandoDobras(() => {});
    expect(dobras.map((d) => d.open)).toEqual([false, false]);
  });

  test("uma dobra sem título aberta não abre as demais sem título", () => {
    dobras = [{ open: true, querySelector: () => null }];
    preservandoDobras(() => {
      dobras = [{ open: false, querySelector: () => null }];
    });
    expect(dobras[0].open).toBe(false);
  });

  test("executa o redesenho mesmo sem dobra nenhuma na tela", () => {
    const redesenhar = jest.fn();
    preservandoDobras(redesenhar);
    expect(redesenhar).toHaveBeenCalledTimes(1);
  });
});

describe("digitandoEmCampo", () => {
  test.each(["INPUT", "TEXTAREA", "SELECT"])("é verdadeiro com o foco num %s", (tag) => {
    expect(digitandoEmCampo({ activeElement: { tagName: tag } })).toBe(true);
  });

  test.each([["BUTTON"], ["BODY"], ["A"]])("é falso com o foco num %s", (tag) => {
    expect(digitandoEmCampo({ activeElement: { tagName: tag } })).toBe(false);
  });

  test("é falso sem nenhum elemento em foco", () => {
    expect(digitandoEmCampo({ activeElement: null })).toBe(false);
  });
});

describe("horaDaAtualizacao", () => {
  test("formata hora e minuto de um instante ISO", () => {
    expect(horaDaAtualizacao("2026-09-30T12:32:00.000Z")).toMatch(/^\d{2}:\d{2}$/);
  });

  test("devolve vazio para uma data inválida ou ausente", () => {
    expect(horaDaAtualizacao("não é data")).toBe("");
    expect(horaDaAtualizacao(null)).toBe("");
  });
});

describe("renderAvisoAnalise", () => {
  test("mostra a pílula com a hora da leitura nova", () => {
    renderAvisoAnalise({ atualizada_em: "2026-09-30T12:32:00.000Z" });
    expect(pilula.classList.contains("hidden")).toBe(false);
    expect(pilula.textContent).toMatch(/^Nova leitura das \d{2}:\d{2} — atualizar$/);
  });

  test("sem hora válida, mostra o texto genérico", () => {
    renderAvisoAnalise({ atualizada_em: null });
    expect(pilula.textContent).toBe("Nova leitura — atualizar");
  });

  test("com null esconde a pílula", () => {
    renderAvisoAnalise({ atualizada_em: "2026-09-30T12:32:00.000Z" });
    renderAvisoAnalise(null);
    expect(pilula.classList.contains("hidden")).toBe(true);
  });
});

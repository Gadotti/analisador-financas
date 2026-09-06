/**
 * web/js/ambiente.js — tela "Configurações".
 *
 * Sem framework de DOM (não há jsdom no projeto): um `document` mínimo, só
 * com os elementos que existem de verdade na tela, é suficiente para
 * exercitar `coletarAmbiente()`. É esse mesmo recorte — o Kimi não tem os
 * campos de fallback nem de busca web, exclusivos da Anthropic — que
 * reproduz a regressão: "Salvar ambiente" lançava `Cannot read properties of
 * null (reading 'value')` porque o laço lia `.value` de um seletor que não
 * existe no bloco do Kimi, sem checar se o elemento foi encontrado.
 */

function elemento(valor = "") {
  return { value: valor };
}

/** Só os campos que a tela realmente tem — o bloco do Kimi não tem tudo. */
function elementosDaTela() {
  return {
    "#e-provedor": elemento("anthropic"),

    "#e-anthropic-chave": elemento(""),
    "#e-anthropic-origem": elemento("arquivo"),
    "#e-anthropic-variavel": elemento(""),
    "#e-anthropic-modelo": elemento("claude-opus-5"),
    "#e-anthropic-effort": elemento("medium"),
    "#e-anthropic-url": elemento(""),
    "#e-anthropic-fallback": elemento(""),
    "#e-anthropic-busca": elemento(""),
    "#e-anthropic-tokens": elemento(""),

    // Kimi não tem #e-kimi-fallback nem #e-kimi-busca no HTML: são exclusivos
    // da Anthropic (fallback e busca web do servidor). É essa ausência que
    // reproduz o bug.
    "#e-kimi-chave": elemento(""),
    "#e-kimi-origem": elemento("arquivo"),
    "#e-kimi-variavel": elemento(""),
    "#e-kimi-modelo": elemento("kimi-k2-thinking"),
    "#e-kimi-effort": elemento("nenhum"),
    "#e-kimi-url": elemento("https://api.moonshot.ai/anthropic"),
    "#e-kimi-tokens": elemento("8000"),

    "#e-telegram-chat": elemento("123456789"),
    "#e-telegram-token": elemento(""),
    "#e-brapi-token": elemento(""),
  };
}

let coletarAmbiente;

beforeAll(async () => {
  global.document = { querySelector: (seletor) => elementosDaTela()[seletor] ?? null };
  ({ coletarAmbiente } = await import("../../web/js/ambiente.js"));
});

afterAll(() => {
  delete global.document;
});

describe("coletarAmbiente", () => {
  test("não lança quando um provedor não tem todos os campos na tela", () => {
    expect(() => coletarAmbiente()).not.toThrow();
  });

  test("bloco do Kimi só traz os campos que existem na tela", () => {
    const { provedores } = coletarAmbiente();

    expect(provedores.kimi.model).toBe("kimi-k2-thinking");
    expect(provedores.kimi.fallback).toBeUndefined();
    expect(provedores.kimi.busca_web).toBeUndefined();
  });

  test("bloco da Anthropic traz todos os campos, já que existem na tela", () => {
    const { provedores } = coletarAmbiente();

    expect(provedores.anthropic.model).toBe("claude-opus-5");
    expect(provedores.anthropic.fallback).toBe("");
    expect(provedores.anthropic.busca_web).toBe("");
  });
});

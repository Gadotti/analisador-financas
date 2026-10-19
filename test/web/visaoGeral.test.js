/**
 * web/js/visaoGeral.js — só o aviso de indicador macro que não é desta
 * execução (`avisoIndicador`), a partir do que `market._valor_de_reserva` grava.
 */

let avisoIndicador;

beforeAll(async () => {
  ({ avisoIndicador } = await import("../../web/js/visaoGeral.js"));
});

describe("avisoIndicador", () => {
  test("consulta de agora bem-sucedida não tem aviso", () => {
    expect(avisoIndicador({ valor: 13.75, fonte: "BCB/SGS 432" })).toBe("");
    expect(avisoIndicador(undefined)).toBe("");
  });

  test("leitura guardada mostra quando foi consultada", () => {
    const aviso = avisoIndicador({
      valor: 13.75,
      fonte: "BCB/SGS 432",
      consultado_em: "2026-10-16T14:20:00",
      erro: "Read timed out",
    });

    expect(aviso).toMatch(/^BCB indisponível · leitura de /);
    expect(aviso).toContain("16/10/2026");
  });

  test("leitura guardada sem hora de consulta ainda é marcada", () => {
    expect(avisoIndicador({ valor: 13.75, fonte: "BCB/SGS 432", erro: "x" })).toBe(
      "BCB indisponível · leitura anterior"
    );
  });

  test("padrão fixo do código é declarado como tal", () => {
    expect(avisoIndicador({ valor: 15, fonte: "padrao", erro: "x" })).toBe(
      "BCB indisponível · valor fixo, não é de hoje"
    );
  });

  test("indicador sem valor diz só que o BCB não respondeu", () => {
    expect(avisoIndicador({ valor: null, fonte: null, erro: "x" })).toBe("BCB indisponível");
  });
});

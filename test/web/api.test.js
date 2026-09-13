/**
 * web/js/api.js — o wrapper de fetch da interface.
 *
 * Sem jsdom (mesmo critério dos demais testes de web/js/): `global.location`
 * é um objeto mínimo, só com `href` gravável, o bastante para conferir o
 * redirecionamento ao login em qualquer 401.
 */

let api;

beforeAll(async () => {
  ({ api } = await import("../../web/js/api.js"));
});

beforeEach(() => {
  global.location = { href: "" };
});

afterEach(() => {
  delete global.fetch;
  delete global.location;
});

describe("api", () => {
  test("devolve o corpo em JSON quando a resposta é ok", async () => {
    global.fetch = async () => ({
      ok: true,
      status: 200,
      json: async () => ({ posicoes: [] }),
    });

    await expect(api("/api/carteira")).resolves.toEqual({ posicoes: [] });
    expect(location.href).toBe("");
  });

  test("em 401, redireciona para /login e lança sem esperar pelo corpo", async () => {
    global.fetch = async () => ({
      ok: false,
      status: 401,
      json: async () => ({ erro: "Autenticação necessária." }),
    });

    await expect(api("/api/carteira")).rejects.toThrow("Autenticação necessária.");
    expect(location.href).toBe("/login");
  });

  test("num erro que não é 401, lança com a mensagem do servidor sem redirecionar", async () => {
    global.fetch = async () => ({
      ok: false,
      status: 422,
      json: async () => ({ erro: "Dado inválido." }),
    });

    await expect(api("/api/posicoes")).rejects.toThrow("Dado inválido.");
    expect(location.href).toBe("");
  });
});

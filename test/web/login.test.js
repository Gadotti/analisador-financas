/**
 * web/js/login.js — só a função `login`, que fala com /api/auth/login.
 *
 * `ligarFormulario` não é exercitada aqui: precisaria de um DOM completo com
 * eventos de submit, e o projeto não traz jsdom (mesmo critério de
 * test/web/ambiente.test.js). A parte que vale testar sem DOM é a chamada
 * HTTP e a mensagem de erro devolvida ao formulário.
 */

let login;
let buscarVersao;

beforeAll(async () => {
  ({ login, buscarVersao } = await import("../../web/js/login.js"));
});

afterEach(() => {
  delete global.fetch;
});

describe("login", () => {
  test("posta usuário e senha em JSON e devolve o corpo em caso de sucesso", async () => {
    const chamadas = [];
    global.fetch = async (rota, opcoes) => {
      chamadas.push([rota, opcoes]);
      return {
        ok: true,
        json: async () => ({ ok: true, usuario: "teste" }),
      };
    };

    const resultado = await login("teste", "senha-123");

    expect(resultado).toEqual({ ok: true, usuario: "teste" });
    expect(chamadas).toHaveLength(1);
    const [rota, opcoes] = chamadas[0];
    expect(rota).toBe("/api/auth/login");
    expect(opcoes.method).toBe("POST");
    expect(JSON.parse(opcoes.body)).toEqual({ usuario: "teste", senha: "senha-123" });
  });

  test("lança com a mensagem de erro do servidor quando a resposta não é ok", async () => {
    global.fetch = async () => ({
      ok: false,
      json: async () => ({ erro: "Usuário ou senha inválidos." }),
    });

    await expect(login("teste", "errada")).rejects.toThrow("Usuário ou senha inválidos.");
  });

  test("usa uma mensagem padrão quando o servidor não devolve 'erro'", async () => {
    global.fetch = async () => ({
      ok: false,
      json: async () => ({}),
    });

    await expect(login("teste", "errada")).rejects.toThrow("Usuário ou senha inválidos.");
  });

  test("usa a mensagem padrão também quando o corpo não é JSON", async () => {
    global.fetch = async () => ({
      ok: false,
      json: async () => {
        throw new Error("não é JSON");
      },
    });

    await expect(login("teste", "errada")).rejects.toThrow("Usuário ou senha inválidos.");
  });
});

describe("buscarVersao", () => {
  test("busca /api/versao sem enviar credencial nenhuma e devolve a versão", async () => {
    const chamadas = [];
    global.fetch = async (rota, opcoes) => {
      chamadas.push([rota, opcoes]);
      return { ok: true, json: async () => ({ versao: "1.2.3" }) };
    };

    await expect(buscarVersao()).resolves.toBe("1.2.3");
    expect(chamadas).toEqual([["/api/versao", undefined]]);
  });

  test("lança quando a resposta não é ok", async () => {
    global.fetch = async () => ({ ok: false, status: 500 });
    await expect(buscarVersao()).rejects.toThrow("Erro 500");
  });
});

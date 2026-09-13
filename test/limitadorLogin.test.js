import * as limitadorLogin from "../src/server/limitadorLogin.js";

afterEach(() => limitadorLogin.reiniciar());

describe("limitadorLogin", () => {
  test("não bloqueia um IP sem tentativas registradas", () => {
    expect(limitadorLogin.bloqueado("1.2.3.4")).toBe(false);
  });

  test("bloqueia depois de MAX_TENTATIVAS falhas na mesma janela", () => {
    const agora = Date.now();
    for (let i = 0; i < limitadorLogin.MAX_TENTATIVAS - 1; i += 1) {
      limitadorLogin.registrarFalha("1.2.3.4", agora);
    }
    expect(limitadorLogin.bloqueado("1.2.3.4", agora)).toBe(false);

    limitadorLogin.registrarFalha("1.2.3.4", agora);
    expect(limitadorLogin.bloqueado("1.2.3.4", agora)).toBe(true);
  });

  test("um IP não afeta o contador de outro", () => {
    const agora = Date.now();
    for (let i = 0; i < limitadorLogin.MAX_TENTATIVAS; i += 1) {
      limitadorLogin.registrarFalha("1.2.3.4", agora);
    }
    expect(limitadorLogin.bloqueado("1.2.3.4", agora)).toBe(true);
    expect(limitadorLogin.bloqueado("5.6.7.8", agora)).toBe(false);
  });

  test("limpar zera o contador (login bem-sucedido)", () => {
    const agora = Date.now();
    for (let i = 0; i < limitadorLogin.MAX_TENTATIVAS; i += 1) {
      limitadorLogin.registrarFalha("1.2.3.4", agora);
    }
    limitadorLogin.limpar("1.2.3.4");
    expect(limitadorLogin.bloqueado("1.2.3.4", agora)).toBe(false);
  });

  test("o bloqueio expira depois da janela", () => {
    const agora = Date.now();
    for (let i = 0; i < limitadorLogin.MAX_TENTATIVAS; i += 1) {
      limitadorLogin.registrarFalha("1.2.3.4", agora);
    }
    expect(limitadorLogin.bloqueado("1.2.3.4", agora)).toBe(true);

    const depoisDaJanela = agora + limitadorLogin.JANELA_MS + 1;
    expect(limitadorLogin.bloqueado("1.2.3.4", depoisDaJanela)).toBe(false);

    // A janela expirada reinicia o contador em vez de acumular com a antiga.
    limitadorLogin.registrarFalha("1.2.3.4", depoisDaJanela);
    expect(limitadorLogin.bloqueado("1.2.3.4", depoisDaJanela)).toBe(false);
  });
});

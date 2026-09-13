import { analisarCookies, cookieLogout, cookieSessao, tokenDaRequisicao } from "../src/server/cookies.js";

describe("analisarCookies", () => {
  test("devolve objeto vazio sem cabeçalho Cookie", () => {
    expect(analisarCookies({ headers: {} })).toEqual({});
  });

  test("lê um único par", () => {
    expect(analisarCookies({ headers: { cookie: "sessao=abc123" } })).toEqual({ sessao: "abc123" });
  });

  test("lê vários pares separados por ponto e vírgula", () => {
    expect(analisarCookies({ headers: { cookie: "a=1; sessao=abc; b=2" } })).toEqual({
      a: "1",
      sessao: "abc",
      b: "2",
    });
  });

  test("decodifica valores com caracteres especiais", () => {
    expect(analisarCookies({ headers: { cookie: "sessao=a%2Fb%3Dc" } })).toEqual({ sessao: "a/b=c" });
  });

  test("ignora pares sem sinal de igual", () => {
    expect(analisarCookies({ headers: { cookie: "invalido; sessao=abc" } })).toEqual({ sessao: "abc" });
  });
});

describe("tokenDaRequisicao", () => {
  test("devolve o valor do cookie de sessão", () => {
    expect(tokenDaRequisicao({ headers: { cookie: "sessao=meu-token" } })).toBe("meu-token");
  });

  test("devolve null quando não há cookie de sessão", () => {
    expect(tokenDaRequisicao({ headers: {} })).toBeNull();
    expect(tokenDaRequisicao({ headers: { cookie: "outro=valor" } })).toBeNull();
  });
});

describe("cookieSessao", () => {
  test("monta o cabeçalho com HttpOnly, SameSite=Strict e o Max-Age em segundos", () => {
    const cabecalho = cookieSessao("meu-token", 30 * 24 * 60 * 60 * 1000);
    expect(cabecalho).toContain("sessao=meu-token");
    expect(cabecalho).toContain("HttpOnly");
    expect(cabecalho).toContain("SameSite=Strict");
    expect(cabecalho).toContain("Path=/");
    expect(cabecalho).toContain(`Max-Age=${30 * 24 * 60 * 60}`);
  });

  test("codifica o token no valor do cookie", () => {
    expect(cookieSessao("a b", 1000)).toContain("sessao=a%20b");
  });
});

describe("cookieLogout", () => {
  test("apaga o cookie de sessão com Max-Age=0", () => {
    const cabecalho = cookieLogout();
    expect(cabecalho).toContain("sessao=;");
    expect(cabecalho).toContain("Max-Age=0");
  });
});

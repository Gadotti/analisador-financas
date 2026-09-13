import crypto from "node:crypto";

import {
  conferirSenha,
  criarToken,
  gerarHashSenha,
  SESSAO_MS,
  tokenValido,
} from "../src/core/authService.js";

describe("hash de senha", () => {
  test("uma senha correta confere com o próprio hash", () => {
    const hash = gerarHashSenha("uma-senha-forte");
    expect(conferirSenha("uma-senha-forte", hash)).toBe(true);
  });

  test("uma senha errada não confere", () => {
    const hash = gerarHashSenha("uma-senha-forte");
    expect(conferirSenha("outra-senha", hash)).toBe(false);
  });

  test("o mesmo texto gera hashes diferentes (sal aleatório)", () => {
    expect(gerarHashSenha("repetida")).not.toBe(gerarHashSenha("repetida"));
  });

  test.each([[""], ["sem-dois-pontos"], ["sal-invalido:"], [":hash-sem-sal"], [null], [undefined]])(
    "hash malformado (%p) nunca confere, nunca lança",
    (hashArmazenado) => {
      expect(() => conferirSenha("qualquer", hashArmazenado)).not.toThrow();
      expect(conferirSenha("qualquer", hashArmazenado)).toBe(false);
    },
  );

  test("hexadecimal inválido (decodifica para 0 bytes) nunca confere", () => {
    // "zz" não é hex válido: Buffer.from ignora e devolve um buffer vazio,
    // mesmo com o texto do campo não sendo vazio.
    expect(conferirSenha("qualquer", "zz:zz")).toBe(false);
  });
});

describe("token de sessão", () => {
  const SEGREDO = "segredo-de-teste";

  test("um token recém-criado é válido", () => {
    const token = criarToken(SEGREDO);
    expect(tokenValido(token, SEGREDO)).toBe(true);
  });

  test("expira depois da duração configurada", () => {
    const agora = Date.now();
    const token = criarToken(SEGREDO, 1000, agora);
    expect(tokenValido(token, SEGREDO, agora + 999)).toBe(true);
    expect(tokenValido(token, SEGREDO, agora + 1001)).toBe(false);
  });

  test("assinado com outro segredo é inválido", () => {
    const token = criarToken(SEGREDO);
    expect(tokenValido(token, "segredo-errado")).toBe(false);
  });

  test("payload adulterado é inválido", () => {
    const token = criarToken(SEGREDO, SESSAO_MS, 1_000_000);
    const [, assinatura] = token.split(".");
    // Mesmo formato do payload original, mas com outra validade — a
    // assinatura antiga não pode passar a valer para um payload diferente.
    const payloadFalso = Buffer.from(JSON.stringify({ exp: 2_000_000 })).toString("base64url");
    expect(tokenValido(`${payloadFalso}.${assinatura}`, SEGREDO)).toBe(false);
  });

  test.each([[""], ["sem-ponto"], [null], [undefined], [123], ["a.b.c"], ["payload-sem-assinatura."]])(
    "token malformado (%p) nunca confere, nunca lança",
    (token) => {
      expect(() => tokenValido(token, SEGREDO)).not.toThrow();
      expect(tokenValido(token, SEGREDO)).toBe(false);
    },
  );

  test("payload corretamente assinado mas que não é JSON é recusado", () => {
    const payloadBase64 = Buffer.from("isto não é um payload json").toString("base64url");
    const assinatura = crypto
      .createHmac("sha256", SEGREDO)
      .update(payloadBase64)
      .digest("base64url");
    expect(tokenValido(`${payloadBase64}.${assinatura}`, SEGREDO)).toBe(false);
  });

  test("sem segredo configurado, nenhum token é válido", () => {
    const token = criarToken(SEGREDO);
    expect(tokenValido(token, null)).toBe(false);
    expect(tokenValido(token, "")).toBe(false);
  });
});

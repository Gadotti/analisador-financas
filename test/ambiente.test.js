import { modeloIa, statusIa, telegramConfigurado } from "../src/server/ambiente.js";
import { comEnv } from "./helpers/ambiente.js";

let restaurar;

afterEach(() => {
  restaurar?.();
  restaurar = null;
});

describe("statusIa", () => {
  test("exige ANTHROPIC_API_KEY", () => {
    restaurar = comEnv({ ANTHROPIC_API_KEY: undefined });
    const { ok, motivo } = statusIa();
    expect(ok).toBe(false);
    expect(motivo).toMatch(/ANTHROPIC_API_KEY/);
  });

  test("fica disponível com a chave configurada", () => {
    restaurar = comEnv({ ANTHROPIC_API_KEY: "sk-ant-teste" });
    expect(statusIa()).toEqual({ ok: true, motivo: "" });
  });
});

describe("modeloIa", () => {
  test("usa o padrão quando não há variável", () => {
    restaurar = comEnv({ ANTHROPIC_MODEL: undefined });
    expect(modeloIa()).toBe("claude-opus-5");
  });

  test("respeita ANTHROPIC_MODEL", () => {
    restaurar = comEnv({ ANTHROPIC_MODEL: "claude-sonnet-5" });
    expect(modeloIa()).toBe("claude-sonnet-5");
  });
});

describe("telegramConfigurado", () => {
  test.each([
    ["sem token nem chat", undefined, undefined, false],
    ["só com token", "123:ABC", undefined, false],
    ["só com chat", undefined, "42", false],
    ["com os dois", "123:ABC", "42", true],
  ])("%s", (_titulo, token, chat, esperado) => {
    restaurar = comEnv({ TELEGRAM_BOT_TOKEN: token, TELEGRAM_CHAT_ID: chat });
    expect(telegramConfigurado()).toBe(esperado);
  });
});

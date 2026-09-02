import { modeloIa, provedorIa, statusIa, telegramConfigurado } from "../src/server/ambiente.js";
import { comEnv, envIaTemporario } from "./helpers/ambiente.js";

const ANTHROPIC_MINIMO = {
  ANTHROPIC_API_KEY: "sk-ant-teste",
  ANTHROPIC_MODEL: "claude-opus-5",
  ANTHROPIC_EFFORT: "medium",
};

let envIa;
let restaurar;

beforeEach(() => {
  envIa = envIaTemporario();
});

afterEach(() => {
  restaurar?.();
  restaurar = null;
  envIa.limpar();
});

describe("statusIa", () => {
  test("fica disponível com o bloco do provedor completo", () => {
    envIa.escrever(ANTHROPIC_MINIMO);
    expect(statusIa()).toEqual({ ok: true, motivo: "" });
  });

  test("exige a chave no arquivo quando a origem é 'arquivo'", () => {
    envIa.escrever({ ANTHROPIC_MODEL: "claude-opus-5", ANTHROPIC_EFFORT: "medium" });
    const { ok, motivo } = statusIa();
    expect(ok).toBe(false);
    expect(motivo).toMatch(/ANTHROPIC_API_KEY/);
  });

  test("ignora a chave do ambiente quando a origem é 'arquivo'", () => {
    restaurar = comEnv({ ANTHROPIC_API_KEY: "sk-ant-do-ambiente" });
    envIa.escrever({
      ANTHROPIC_ORIGEM_CHAVE: "arquivo",
      ANTHROPIC_MODEL: "claude-opus-5",
      ANTHROPIC_EFFORT: "medium",
    });
    expect(statusIa().motivo).toMatch(/somente do arquivo/);
  });

  test("busca a chave na variável de ambiente nomeada no arquivo", () => {
    restaurar = comEnv({ CHAVE_CORPORATIVA: "sk-ant-do-ambiente" });
    envIa.escrever({
      ANTHROPIC_ORIGEM_CHAVE: "ambiente",
      ANTHROPIC_VARIAVEL_CHAVE: "CHAVE_CORPORATIVA",
      ANTHROPIC_MODEL: "claude-opus-5",
      ANTHROPIC_EFFORT: "medium",
    });
    expect(statusIa()).toEqual({ ok: true, motivo: "" });
  });

  test("falha quando a variável de ambiente indicada não existe", () => {
    restaurar = comEnv({ CHAVE_AUSENTE: undefined });
    envIa.escrever({
      ANTHROPIC_ORIGEM_CHAVE: "ambiente",
      ANTHROPIC_VARIAVEL_CHAVE: "CHAVE_AUSENTE",
      ANTHROPIC_MODEL: "claude-opus-5",
      ANTHROPIC_EFFORT: "medium",
    });
    expect(statusIa().motivo).toMatch(/CHAVE_AUSENTE/);
  });

  test("exige o nome da variável quando a origem é 'ambiente'", () => {
    envIa.escrever({ ANTHROPIC_ORIGEM_CHAVE: "ambiente", ...ANTHROPIC_MINIMO });
    expect(statusIa().motivo).toMatch(/ANTHROPIC_VARIAVEL_CHAVE/);
  });

  test("recusa origem desconhecida", () => {
    envIa.escrever({ ANTHROPIC_ORIGEM_CHAVE: "cofre", ...ANTHROPIC_MINIMO });
    expect(statusIa().motivo).toMatch(/ORIGEM_CHAVE inválida/);
  });

  test("exige modelo e esforço, que não têm padrão no código", () => {
    envIa.escrever({ ANTHROPIC_API_KEY: "sk-ant-teste" });
    expect(statusIa().motivo).toMatch(/ANTHROPIC_MODEL/);

    envIa.escrever({ ANTHROPIC_API_KEY: "sk-ant-teste", ANTHROPIC_MODEL: "claude-opus-5" });
    expect(statusIa().motivo).toMatch(/ANTHROPIC_EFFORT/);
  });
});

describe("modeloIa e provedorIa", () => {
  test("vêm do arquivo, que tem precedência sobre o ambiente", () => {
    restaurar = comEnv({ ANTHROPIC_MODEL: "claude-opus-5" });
    envIa.escrever({ ANTHROPIC_MODEL: "claude-sonnet-5", ANTHROPIC_EFFORT: "high" });
    expect(modeloIa()).toBe("claude-sonnet-5");
    expect(provedorIa()).toBe("anthropic");
  });

  test("caem no ambiente quando o arquivo não define", () => {
    restaurar = comEnv({ ANTHROPIC_MODEL: "claude-fable-5", ANTHROPIC_EFFORT: "xhigh" });
    expect(modeloIa()).toBe("claude-fable-5");
  });

  test("seguem o bloco do provedor escolhido em IA_PROVEDOR", () => {
    envIa.escrever({
      IA_PROVEDOR: "kimi",
      KIMI_API_KEY: "sk-kimi-teste",
      KIMI_MODEL: "kimi-k2-thinking",
      KIMI_EFFORT: "nenhum",
    });
    expect(provedorIa()).toBe("kimi");
    expect(modeloIa()).toBe("kimi-k2-thinking");
    expect(statusIa()).toEqual({ ok: true, motivo: "" });
  });

  test("recusam um IA_PROVEDOR que não vira prefixo", () => {
    envIa.escrever({ IA_PROVEDOR: "---" });
    expect(statusIa().motivo).toMatch(/IA_PROVEDOR inválido/);
    expect(modeloIa()).toBeNull();
  });

  test("são nulos quando o .env não define nada", () => {
    restaurar = comEnv({ ANTHROPIC_MODEL: undefined, ANTHROPIC_EFFORT: undefined });
    expect(modeloIa()).toBeNull();
    expect(provedorIa()).toBeNull();
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

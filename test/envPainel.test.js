import { ConfiguracaoIaError } from "../src/config/configIa.js";
import { lerPainelEnv, salvarPainelEnv } from "../src/config/envPainel.js";
import { comEnv, envIaTemporario } from "./helpers/ambiente.js";

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

describe("lerPainelEnv", () => {
  test("devolve os dois blocos de provedor vazios quando o .env não existe", () => {
    const dados = lerPainelEnv();
    expect(dados.ia_provedor).toBe("");
    expect(dados.provedores.anthropic).toEqual({
      origem_chave: "",
      variavel_chave: "",
      model: "",
      effort: "",
      base_url: "",
      fallback: "",
      busca_web: "",
      max_tokens: "",
      api_key_definida: false,
    });
    expect(dados.telegram).toEqual({ chat_id: "", bot_token_definido: false });
    expect(dados.brapi_token_definido).toBe(false);
  });

  test("nunca devolve o valor da chave, só a presença", () => {
    envIa.escrever({ ANTHROPIC_API_KEY: "sk-ant-secreta" });
    const dados = lerPainelEnv();
    expect(dados.provedores.anthropic.api_key_definida).toBe(true);
    expect(JSON.stringify(dados)).not.toMatch(/sk-ant-secreta/);
  });

  test("lê o bloco Kimi e o provedor ativo", () => {
    envIa.escrever({
      IA_PROVEDOR: "kimi",
      KIMI_MODEL: "kimi-k2-thinking",
      KIMI_EFFORT: "nenhum",
      KIMI_API_KEY: "sk-kimi-secreta",
    });
    const dados = lerPainelEnv();
    expect(dados.ia_provedor).toBe("kimi");
    expect(dados.provedores.kimi.model).toBe("kimi-k2-thinking");
    expect(dados.provedores.kimi.api_key_definida).toBe(true);
  });

  test("informa token do Telegram e da brapi sem devolver o valor", () => {
    envIa.escrever({
      TELEGRAM_BOT_TOKEN: "123:ABC",
      TELEGRAM_CHAT_ID: "42",
      BRAPI_TOKEN: "token-brapi",
    });
    const dados = lerPainelEnv();
    expect(dados.telegram).toEqual({ chat_id: "42", bot_token_definido: true });
    expect(dados.brapi_token_definido).toBe(true);
    expect(JSON.stringify(dados)).not.toMatch(/123:ABC|token-brapi/);
  });
});

describe("salvarPainelEnv", () => {
  test("grava o modelo e a chave informados", () => {
    const dados = salvarPainelEnv({
      ia_provedor: "anthropic",
      provedores: {
        anthropic: { model: "claude-sonnet-5", effort: "medium", api_key: "sk-ant-nova" },
      },
    });
    expect(dados.ia_provedor).toBe("anthropic");
    expect(dados.provedores.anthropic.model).toBe("claude-sonnet-5");
    expect(dados.provedores.anthropic.api_key_definida).toBe(true);
  });

  test("chave em branco mantém a já gravada", () => {
    envIa.escrever({ ANTHROPIC_API_KEY: "sk-ant-antiga", ANTHROPIC_MODEL: "claude-opus-5" });
    const dados = salvarPainelEnv({
      provedores: { anthropic: { model: "claude-sonnet-5", api_key: "" } },
    });
    expect(dados.provedores.anthropic.model).toBe("claude-sonnet-5");
    expect(dados.provedores.anthropic.api_key_definida).toBe(true);
  });

  test("token do Telegram em branco mantém o já gravado", () => {
    envIa.escrever({ TELEGRAM_BOT_TOKEN: "123:ABC" });
    const dados = salvarPainelEnv({ telegram: { chat_id: "99", bot_token: "" } });
    expect(dados.telegram).toEqual({ chat_id: "99", bot_token_definido: true });
  });

  test("grava um novo token do Telegram quando informado", () => {
    const dados = salvarPainelEnv({ telegram: { bot_token: "999:NOVO" } });
    expect(dados.telegram.bot_token_definido).toBe(true);
  });

  test("grava o token da brapi quando informado e o mantém quando em branco", () => {
    const primeiro = salvarPainelEnv({ brapi_token: "token-1" });
    expect(primeiro.brapi_token_definido).toBe(true);

    const segundo = salvarPainelEnv({ brapi_token: "" });
    expect(segundo.brapi_token_definido).toBe(true);
  });

  test("recusa um IA_PROVEDOR que não vira prefixo válido", () => {
    expect(() => salvarPainelEnv({ ia_provedor: "---" })).toThrow(ConfiguracaoIaError);
  });

  test("atualiza process.env para refletir a gravação sem reiniciar o servidor", () => {
    restaurar = comEnv({ TELEGRAM_CHAT_ID: undefined });
    salvarPainelEnv({ telegram: { chat_id: "555" } });
    expect(process.env.TELEGRAM_CHAT_ID).toBe("555");
  });
});

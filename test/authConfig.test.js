import { AutenticacaoError, arquivoEnvAuth, configuracaoAuth } from "../src/config/authConfig.js";
import { authEnvTemporario, credenciaisAuthExemplo } from "./helpers/ambiente.js";

let authEnv;

afterEach(() => {
  authEnv?.limpar();
  authEnv = undefined;
});

describe("configuracaoAuth", () => {
  test("lê usuário, hash e segredo do .env apontado por AUTH_ENV_FILE", () => {
    const credenciais = credenciaisAuthExemplo("admin", "senha-123456");
    authEnv = authEnvTemporario(credenciais.variaveis);

    expect(configuracaoAuth()).toEqual({
      usuario: "admin",
      senhaHash: credenciais.variaveis.AUTH_SENHA_HASH,
      segredoSessao: "segredo-de-teste-para-assinatura-hmac",
    });
  });

  test("arquivoEnvAuth aponta para AUTH_ENV_FILE quando definido", () => {
    authEnv = authEnvTemporario();
    expect(arquivoEnvAuth()).toBe(authEnv.arquivo);
  });

  test.each([["AUTH_USUARIO"], ["AUTH_SENHA_HASH"], ["AUTH_SESSAO_SEGREDO"]])(
    "lança AutenticacaoError quando falta %s",
    (chaveAusente) => {
      const { variaveis } = credenciaisAuthExemplo();
      delete variaveis[chaveAusente];
      authEnv = authEnvTemporario(variaveis);

      expect(() => configuracaoAuth()).toThrow(AutenticacaoError);
      expect(() => configuracaoAuth()).toThrow(chaveAusente);
    },
  );

  test("a mensagem de erro aponta o script de criação do login", () => {
    authEnv = authEnvTemporario({});
    expect(() => configuracaoAuth()).toThrow(/criarLogin\.js/);
  });

  test("valores em branco contam como ausentes", () => {
    authEnv = authEnvTemporario({ AUTH_USUARIO: "  ", AUTH_SENHA_HASH: "x", AUTH_SESSAO_SEGREDO: "y" });
    expect(() => configuracaoAuth()).toThrow(/AUTH_USUARIO/);
  });
});

import fs from "node:fs";

import { jest } from "@jest/globals";

import { usuariosFile } from "../src/config/paths.js";
import {
  abrirNavegador,
  comandoNavegador,
  HOST,
  iniciar,
  PORTA_PADRAO,
  parseArgs,
} from "../src/server/index.js";
import { dataDirTemporario, usuarioAuthExemplo } from "./helpers/ambiente.js";

let ambiente;
let credenciais;
let servidores = [];

beforeAll(() => {
  ambiente = dataDirTemporario();
  credenciais = usuarioAuthExemplo(ambiente.dir);
});
afterAll(() => {
  ambiente.limpar();
});

afterEach(async () => {
  await Promise.all(servidores.filter(Boolean).map((s) => new Promise((resolve) => s.close(resolve))));
  servidores = [];
  process.exitCode = 0;
});

const subir = (args) => {
  const servidor = iniciar(args);
  servidores.push(servidor);
  return servidor;
};

describe("parseArgs", () => {
  test("usa a porta padrão sem argumentos", () => {
    expect(parseArgs([])).toEqual({ porta: PORTA_PADRAO, semNavegador: false });
  });

  test("aceita --porta e --sem-navegador", () => {
    expect(parseArgs(["--porta", "9000", "--sem-navegador"])).toEqual({
      porta: 9000,
      semNavegador: true,
    });
  });

  test("aceita a porta 0 (efêmera)", () => {
    expect(parseArgs(["--porta", "0"]).porta).toBe(0);
  });

  test.each([
    [["--porta", "abc"], /Porta inválida/],
    [["--porta", "99999"], /Porta inválida/],
    [["--turbo"], /Opção desconhecida/],
  ])("rejeita %p", (args, mensagem) => {
    expect(() => parseArgs(args)).toThrow(mensagem);
  });
});

describe("comandoNavegador", () => {
  test.each([
    ["win32", 'start "" "http://x"'],
    ["darwin", 'open "http://x"'],
    ["linux", 'xdg-open "http://x"'],
  ])("monta o comando de %s", (plataforma, esperado) => {
    expect(comandoNavegador("http://x", plataforma)).toBe(esperado);
  });
});

describe("abrirNavegador", () => {
  // Nenhum teste executa o comando de verdade: o executor é injetado.
  test("delega o comando ao executor injetado, sem abrir nada", () => {
    const executar = jest.fn();
    abrirNavegador("http://127.0.0.1:9999", { executar });

    expect(executar).toHaveBeenCalledTimes(1);
    expect(executar.mock.calls[0][0]).toBe(comandoNavegador("http://127.0.0.1:9999"));
    expect(typeof executar.mock.calls[0][1]).toBe("function");
  });
});

describe("iniciar", () => {
  test("sobe normalmente mesmo sem usuário cadastrado — só a tela de login aparece", async () => {
    fs.rmSync(usuariosFile(), { force: true });

    const servidor = subir(["--porta", "0", "--sem-navegador"]);
    await new Promise((resolve) => servidor.once("listening", resolve));
    const base = `http://${HOST}:${servidor.address().port}`;

    const semLogin = await fetch(`${base}/`, { redirect: "manual" });
    expect(semLogin.status).toBe(302);
    expect(semLogin.headers.get("location")).toBe("/login");

    const tentativa = await fetch(`${base}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ usuario: "qualquer", senha: "qualquer" }),
    });
    expect(tentativa.status).toBe(500);
    expect((await tentativa.json()).erro).toMatch(/criarLogin\.js/);

    credenciais = usuarioAuthExemplo(ambiente.dir); // restaura para os testes seguintes
  });

  test("sobe em 127.0.0.1 numa porta efêmera e responde à API autenticada", async () => {
    const servidor = subir(["--porta", "0", "--sem-navegador"]);
    await new Promise((resolve) => servidor.once("listening", resolve));

    const { address, port } = servidor.address();
    expect(address).toBe(HOST);
    const base = `http://${HOST}:${port}`;

    const semSessao = await fetch(`${base}/api/status`);
    expect(semSessao.status).toBe(401);

    const login = await fetch(`${base}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ usuario: credenciais.usuario, senha: credenciais.senha }),
    });
    const cookie = login.headers.get("set-cookie").split(";")[0];

    const resposta = await fetch(`${base}/api/status`, { headers: { Cookie: cookie } });
    expect(resposta.status).toBe(200);

    const corpo = await resposta.json();
    expect(typeof corpo.ia_disponivel).toBe("boolean");
    expect(typeof corpo.modelo).toBe("string");
  });

  test("relata porta ocupada em vez de estourar", async () => {
    const primeiro = subir(["--porta", "0", "--sem-navegador"]);
    await new Promise((resolve) => primeiro.once("listening", resolve));

    const segundo = subir(["--porta", String(primeiro.address().port), "--sem-navegador"]);
    const erro = await new Promise((resolve) => segundo.once("error", resolve));

    expect(erro.code).toBe("EADDRINUSE");
    process.exitCode = 0; // o handler sinalizou falha; o teste em si passou
  });
});

import { jest } from "@jest/globals";

import {
  abrirNavegador,
  comandoNavegador,
  HOST,
  iniciar,
  PORTA_PADRAO,
  parseArgs,
} from "../src/server/index.js";
import { dataDirTemporario } from "./helpers/ambiente.js";

let ambiente;
let servidores = [];

beforeAll(() => {
  ambiente = dataDirTemporario();
});
afterAll(() => ambiente.limpar());

afterEach(async () => {
  await Promise.all(servidores.map((s) => new Promise((resolve) => s.close(resolve))));
  servidores = [];
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
  test("sobe em 127.0.0.1 numa porta efêmera e responde à API", async () => {
    const servidor = subir(["--porta", "0", "--sem-navegador"]);
    await new Promise((resolve) => servidor.once("listening", resolve));

    const { address, port } = servidor.address();
    expect(address).toBe(HOST);

    const resposta = await fetch(`http://${HOST}:${port}/api/status`);
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

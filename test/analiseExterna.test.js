/**
 * Ponte entre o servidor e o script Python.
 *
 * Os testes disparam scripts Python mínimos, escritos num diretório
 * temporário: exercitam o contrato (JSON no stdout, progresso no stderr,
 * campo `erro`, tempo limite) sem depender do motor de análise nem da rede.
 */

import fs from "node:fs";
import path from "node:path";

import {
  enviarUltimaAoTelegram,
  executarAnalise,
  interpretadorPython,
  rodarScript,
  testarTelegram,
} from "../src/server/analiseExterna.js";
import { comEnv, dataDirTemporario } from "./helpers/ambiente.js";

let ambiente;

beforeAll(() => {
  ambiente = dataDirTemporario();
});
afterAll(() => ambiente.limpar());

/** Escreve um script Python auxiliar e devolve o caminho. */
function scriptPython(nome, corpo) {
  const destino = path.join(ambiente.dir, nome);
  fs.writeFileSync(destino, corpo, "utf8");
  return destino;
}

const ECOA_ARGS = [
  "import json, sys",
  'print(json.dumps({"args": sys.argv[1:]}))',
].join("\n");

describe("interpretadorPython", () => {
  test("respeita PYTHON_BIN quando definido", () => {
    const restaurar = comEnv({ PYTHON_BIN: "C:/venv/Scripts/python.exe" });
    try {
      expect(interpretadorPython()).toBe("C:/venv/Scripts/python.exe");
    } finally {
      restaurar();
    }
  });

  test("cai no executável padrão da plataforma", () => {
    const restaurar = comEnv({ PYTHON_BIN: undefined });
    try {
      expect(interpretadorPython()).toBe(process.platform === "win32" ? "python" : "python3");
    } finally {
      restaurar();
    }
  });
});

describe("rodarScript", () => {
  test("devolve o JSON impresso pelo script", async () => {
    const script = scriptPython("ok.py", 'print(\'{"ok": true}\')');
    await expect(rodarScript([], { script })).resolves.toEqual({ ok: true });
  });

  test("acrescenta --json e repassa as demais flags", async () => {
    const script = scriptPython("args.py", ECOA_ARGS);
    const { args } = await rodarScript(["--sem-ia"], { script });
    expect(args).toEqual(["--json", "--sem-ia"]);
  });

  test("lê apenas a última linha do stdout", async () => {
    const script = scriptPython(
      "ruidoso.py",
      ['print("aviso solto")', 'print(\'{"ok": true}\')'].join("\n"),
    );
    await expect(rodarScript([], { script })).resolves.toEqual({ ok: true });
  });

  test("encaminha o progresso do stderr linha a linha", async () => {
    const script = scriptPython(
      "progresso.py",
      [
        "import sys",
        'print("[1/3] carregando", file=sys.stderr)',
        'print("[2/3] analisando", file=sys.stderr)',
        'print(\'{"ok": true}\')',
      ].join("\n"),
    );

    const linhas = [];
    await rodarScript([], { script, aoRegistrar: (l) => linhas.push(l) });
    expect(linhas).toEqual(["[1/3] carregando", "[2/3] analisando"]);
  });

  test("rejeita quando o JSON traz um campo de erro", async () => {
    const script = scriptPython("erro.py", 'print(\'{"erro": "algo deu errado"}\')');
    await expect(rodarScript([], { script })).rejects.toThrow("algo deu errado");
  });

  test("rejeita quando a saída não é JSON", async () => {
    const script = scriptPython("lixo.py", 'print("nada de json")');
    await expect(rodarScript([], { script })).rejects.toThrow(/saída inválida/);
  });

  test("rejeita quando o script não produz saída", async () => {
    const script = scriptPython(
      "vazio.py",
      ["import sys", 'print("faltou uma variavel", file=sys.stderr)', "sys.exit(1)"].join("\n"),
    );
    await expect(rodarScript([], { script })).rejects.toThrow(/sem produzir resultado/);
  });

  test("rejeita quando o tempo limite estoura", async () => {
    const script = scriptPython("lento.py", ["import time", "time.sleep(30)"].join("\n"));
    await expect(rodarScript([], { script, timeoutMs: 300 })).rejects.toThrow(/tempo limite/);
  });

  test("explica quando o interpretador Python não existe", async () => {
    const script = scriptPython("ok.py", 'print(\'{"ok": true}\')');
    await expect(
      rodarScript([], { script, python: "python-que-nao-existe" }),
    ).rejects.toThrow(/Python não encontrado/);
  });
});

describe("atalhos", () => {
  let script;

  beforeAll(() => {
    script = scriptPython("atalhos.py", ECOA_ARGS);
  });

  test.each([
    ["análise com IA", () => executarAnalise({ usarIa: true, script }), ["--json"]],
    ["análise sem IA", () => executarAnalise({ usarIa: false, script }), ["--json", "--sem-ia"]],
    ["reenvio ao Telegram", () => enviarUltimaAoTelegram({ script }), ["--json", "--enviar-ultima"]],
    ["teste do Telegram", () => testarTelegram({ script }), ["--json", "--testar-telegram"]],
  ])("%s monta as flags corretas", async (_titulo, chamar, esperado) => {
    const { args } = await chamar();
    expect(args).toEqual(esperado);
  });
});

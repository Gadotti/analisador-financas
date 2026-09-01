import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import {
  agoraISO,
  diferencaDias,
  hoje,
  paraData,
  paraISO,
  somarDias,
} from "../src/util/datas.js";
import { carregarEnv } from "../src/util/env.js";
import { comEnv } from "./helpers/ambiente.js";

const NL = String.fromCharCode(10);

describe("datas", () => {
  test("converte ISO para Date em UTC", () => {
    const d = paraData("2026-03-15");
    expect(d.getUTCFullYear()).toBe(2026);
    expect(d.getUTCMonth()).toBe(2);
    expect(d.getUTCDate()).toBe(15);
  });

  test("aceita ISO com hora e ignora o horário", () => {
    expect(paraISO(paraData("2026-03-15T23:59:59"))).toBe("2026-03-15");
  });

  test.each([["15/03/2026"], ["2026-02-30"], ["2026-13-01"], [null], [""]])(
    "rejeita a data inválida %p",
    (valor) => {
      expect(() => paraData(valor)).toThrow(RangeError);
    },
  );

  test("soma dias atravessando a virada de mês e de ano", () => {
    expect(paraISO(somarDias(paraData("2026-12-31"), 1))).toBe("2027-01-01");
    expect(paraISO(somarDias(paraData("2026-03-01"), -1))).toBe("2026-02-28");
  });

  test("mede a diferença em dias corridos", () => {
    expect(diferencaDias(paraData("2026-01-01"), paraData("2026-01-31"))).toBe(30);
    expect(diferencaDias(paraData("2026-01-31"), paraData("2026-01-01"))).toBe(-30);
  });

  test("hoje devolve meia-noite UTC do dia local", () => {
    const d = hoje();
    expect(d.getUTCHours()).toBe(0);
    expect(d.getUTCDate()).toBe(new Date().getDate());
  });

  test("agoraISO formata sem fuso e com segundos", () => {
    expect(agoraISO(new Date(2026, 8, 1, 7, 4, 9))).toBe("2026-09-01T07:04:09");
  });
});

describe("carregarEnv", () => {
  let dir;

  beforeEach(() => {
    dir = fs.mkdtempSync(path.join(os.tmpdir(), "env-"));
  });
  afterEach(() => {
    fs.rmSync(dir, { recursive: true, force: true });
  });

  const escrever = (conteudo) => {
    const arquivo = path.join(dir, ".env");
    fs.writeFileSync(arquivo, conteudo);
    return arquivo;
  };

  test("devolve false quando o arquivo não existe", () => {
    expect(carregarEnv(path.join(dir, "nao-existe"))).toBe(false);
  });

  test("lê pares chave=valor sem sobrescrever o ambiente já definido", () => {
    const arquivo = escrever(
      ["# comentário", 'TESTE_NOVO="valor com espaço"', "TESTE_EXISTENTE=do-arquivo"].join("\n"),
    );

    const restaurar = comEnv({ TESTE_EXISTENTE: "do-ambiente", TESTE_NOVO: undefined });
    try {
      expect(carregarEnv(arquivo)).toBe(true);
      expect(process.env.TESTE_NOVO).toBe("valor com espaço");
      expect(process.env.TESTE_EXISTENTE).toBe("do-ambiente");
    } finally {
      restaurar();
    }
  });

  test("interpreta comentários, export e aspas; ignora linhas sem igual", () => {
    const arquivo = escrever(
      [
        "# comentário",
        "",
        "export EXPORTADA=valor-exportado",
        "SIMPLES=sem-aspas",
        "ASPAS_SIMPLES='entre aspas'",
        "linha sem igual",
      ].join(NL),
    );

    const restaurar = comEnv({
      EXPORTADA: undefined,
      SIMPLES: undefined,
      ASPAS_SIMPLES: undefined,
    });

    try {
      expect(carregarEnv(arquivo)).toBe(true);
      expect(process.env.EXPORTADA).toBe("valor-exportado");
      expect(process.env.SIMPLES).toBe("sem-aspas");
      expect(process.env.ASPAS_SIMPLES).toBe("entre aspas");
    } finally {
      restaurar();
    }
  });

  test("aceita valor vazio e valor com sinal de igual", () => {
    const arquivo = escrever(["VAZIA=", "COM_IGUAL=a=b=c"].join(NL));
    const restaurar = comEnv({ VAZIA: undefined, COM_IGUAL: undefined });
    try {
      carregarEnv(arquivo);
      expect(process.env.VAZIA).toBe("");
      expect(process.env.COM_IGUAL).toBe("a=b=c");
    } finally {
      restaurar();
    }
  });
});

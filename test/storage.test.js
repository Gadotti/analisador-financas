import fs from "node:fs";
import path from "node:path";

import { execucoesFile, historyDir, lastAnalysisFile } from "../src/config/paths.js";
import { execucoes, historico, ultimaAnalise } from "../src/core/storage.js";
import { dataDirTemporario, gravarAnalise, snapshotExemplo } from "./helpers/ambiente.js";

let ambiente;

beforeAll(() => {
  ambiente = dataDirTemporario();
});
afterAll(() => ambiente.limpar());
beforeEach(() => {
  fs.rmSync(lastAnalysisFile(), { force: true });
  fs.rmSync(execucoesFile(), { force: true });
  fs.rmSync(historyDir(), { recursive: true, force: true });
  fs.mkdirSync(historyDir(), { recursive: true });
});

const gravarExecucoes = (registros) =>
  fs.writeFileSync(execucoesFile(), JSON.stringify(registros), "utf8");

const gravar = (data, valorAtual = 22000) => {
  const base = snapshotExemplo();
  return gravarAnalise(ambiente.dir, {
    ...base,
    data,
    totais: { ...base.totais, valor_atual: valorAtual },
  });
};

describe("ultimaAnalise", () => {
  test("lê o registro gravado pela análise", () => {
    gravar("2026-09-01");
    expect(ultimaAnalise().snapshot.data).toBe("2026-09-01");
  });

  test("devolve null quando não há análise salva", () => {
    expect(ultimaAnalise()).toBeNull();
  });

  test("devolve null quando o arquivo está corrompido", () => {
    fs.writeFileSync(lastAnalysisFile(), "{{{");
    expect(ultimaAnalise()).toBeNull();
  });
});

describe("historico", () => {
  test("devolve a série em ordem cronológica", () => {
    gravar("2026-08-30", 1000);
    gravar("2026-09-01", 3000);
    gravar("2026-08-31", 2000);

    const serie = historico();
    expect(serie.map((s) => s.data)).toEqual(["2026-08-30", "2026-08-31", "2026-09-01"]);
    expect(serie.map((s) => s.valor_atual)).toEqual([1000, 2000, 3000]);
    expect(serie[0].saude).toBe("boa");
  });

  test("respeita o limite mantendo os registros mais recentes", () => {
    for (let dia = 1; dia <= 5; dia += 1) gravar(`2026-09-0${dia}`, dia * 100);
    expect(historico(2).map((s) => s.data)).toEqual(["2026-09-04", "2026-09-05"]);
  });

  test("ignora registros corrompidos ou de outro formato", () => {
    gravar("2026-09-01");
    fs.writeFileSync(path.join(historyDir(), "2026-09-02.json"), "não é json");
    fs.writeFileSync(path.join(historyDir(), "2026-09-03.json"), JSON.stringify({ outro: 1 }));
    fs.writeFileSync(path.join(historyDir(), "leia-me.txt"), "ignorado");

    const serie = historico();
    expect(serie).toHaveLength(1);
    expect(serie[0].data).toBe("2026-09-01");
  });

  test("devolve lista vazia quando o diretório não existe", () => {
    fs.rmSync(historyDir(), { recursive: true, force: true });
    expect(historico()).toEqual([]);
  });
});

describe("execucoes", () => {
  test("lê o log na ordem em que o Python gravou", () => {
    gravarExecucoes([
      { gerado_em: "2026-09-07T07:18:37", status_ia: "erro" },
      { gerado_em: "2026-09-07T08:31:19", status_ia: "sucesso" },
    ]);

    const log = execucoes();
    expect(log.map((e) => e.status_ia)).toEqual(["erro", "sucesso"]);
  });

  test("respeita o limite mantendo as execuções mais recentes", () => {
    gravarExecucoes([1, 2, 3, 4].map((n) => ({ gerado_em: `2026-09-0${n}T10:00:00` })));
    expect(execucoes(2).map((e) => e.gerado_em)).toEqual([
      "2026-09-03T10:00:00",
      "2026-09-04T10:00:00",
    ]);
  });

  test("devolve lista vazia sem arquivo, corrompido ou de outro formato", () => {
    expect(execucoes()).toEqual([]);
    fs.writeFileSync(execucoesFile(), "{{{");
    expect(execucoes()).toEqual([]);
    gravarExecucoes({ nao: "e uma lista" });
    expect(execucoes()).toEqual([]);
  });
});

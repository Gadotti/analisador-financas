import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";

import { criarBackupZip } from "../src/server/backup.js";
import { dataDirTemporario } from "./helpers/ambiente.js";

/** Lê as entradas de um buffer .zip pelos cabeçalhos locais — não há lib de zip no projeto. */
function extrairZip(buffer) {
  const arquivos = {};
  let offset = 0;
  while (offset + 4 <= buffer.length && buffer.readUInt32LE(offset) === 0x04034b50) {
    const metodo = buffer.readUInt16LE(offset + 8);
    const tamanhoComprimido = buffer.readUInt32LE(offset + 18);
    const tamanhoOriginal = buffer.readUInt32LE(offset + 22);
    const tamanhoNome = buffer.readUInt16LE(offset + 26);
    const tamanhoExtra = buffer.readUInt16LE(offset + 28);
    const inicioNome = offset + 30;
    const nome = buffer.subarray(inicioNome, inicioNome + tamanhoNome).toString("utf8");
    const inicioDados = inicioNome + tamanhoNome + tamanhoExtra;
    const dados = buffer.subarray(inicioDados, inicioDados + tamanhoComprimido);
    arquivos[nome] = metodo === 8 ? zlib.inflateRawSync(dados) : dados;
    expect(arquivos[nome]).toHaveLength(tamanhoOriginal);
    offset = inicioDados + tamanhoComprimido;
  }
  return arquivos;
}

let ambiente;

beforeEach(() => {
  ambiente = dataDirTemporario();
});

afterEach(() => {
  ambiente.limpar();
});

test("compacta os arquivos de data/ num .zip legível, num nível só de compactação", () => {
  fs.writeFileSync(path.join(ambiente.dir, "portfolio.json"), '{"posicoes":[]}', "utf8");
  fs.writeFileSync(path.join(ambiente.dir, "history", "2026-09-15.json"), '{"data":"2026-09-15"}', "utf8");

  const arquivos = extrairZip(criarBackupZip());

  expect(arquivos["portfolio.json"].toString("utf8")).toBe('{"posicoes":[]}');
  expect(arquivos["history/2026-09-15.json"].toString("utf8")).toBe('{"data":"2026-09-15"}');
});

test("exclui usuarios.json — hash de senha e segredo de sessão são dado Restrito", () => {
  fs.writeFileSync(path.join(ambiente.dir, "portfolio.json"), "{}", "utf8");
  fs.writeFileSync(
    path.join(ambiente.dir, "usuarios.json"),
    '{"segredo_sessao":"x","usuarios":[]}',
    "utf8"
  );

  const arquivos = extrairZip(criarBackupZip());

  expect(arquivos["portfolio.json"]).toBeDefined();
  expect(arquivos["usuarios.json"]).toBeUndefined();
});

test("exclui .gitkeep em qualquer subpasta — é placeholder do Git, não dado do usuário", () => {
  fs.writeFileSync(path.join(ambiente.dir, ".gitkeep"), "", "utf8");
  fs.writeFileSync(path.join(ambiente.dir, "history", ".gitkeep"), "", "utf8");
  fs.writeFileSync(path.join(ambiente.dir, "portfolio.json"), "{}", "utf8");

  const arquivos = extrairZip(criarBackupZip());

  expect(arquivos["portfolio.json"]).toBeDefined();
  expect(arquivos[".gitkeep"]).toBeUndefined();
  expect(arquivos["history/.gitkeep"]).toBeUndefined();
});

test("um data/ vazio gera um .zip válido, sem entradas", () => {
  const zip = criarBackupZip();
  expect(zip.readUInt32LE(0)).toBe(0x06054b50); // só o EOCD, sem cabeçalho local nenhum
  expect(extrairZip(zip)).toEqual({});
});

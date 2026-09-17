/**
 * Empacota o diretório `data/` num .zip para o botão "Backup" baixar.
 *
 * Sem dependência de produção (nada de `archiver`, `yazl` ou `tar`): o
 * arquivo ZIP é montado à mão (cabeçalhos locais, diretório central e EOCD)
 * usando só `zlib.deflateRawSync`, nativo do Node — funciona igual em amd64 e
 * arm64, porque não há binário externo nem addon nativo envolvido, só zlib
 * (compilado dentro do próprio Node) e Buffer puro.
 */

import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";

import { dataDir } from "../config/paths.js";

const ASSINATURA_LOCAL = 0x04034b50;
const ASSINATURA_CENTRAL = 0x02014b50;
const ASSINATURA_FIM = 0x06054b50;
const METODO_DEFLATE = 8;

/** Guarda hash de senha e segredo de sessão (dado Restrito) — nunca entra no backup baixável. */
const ARQUIVOS_EXCLUIDOS = new Set(["usuarios.json"]);

/** Placeholder do Git para a pasta vazia — não é dado do usuário. */
const NOMES_EXCLUIDOS = new Set([".gitkeep"]);

const TABELA_CRC32 = (() => {
  const tabela = new Uint32Array(256);
  for (let n = 0; n < 256; n += 1) {
    let c = n;
    for (let k = 0; k < 8; k += 1) {
      c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
    tabela[n] = c >>> 0;
  }
  return tabela;
})();

function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc = TABELA_CRC32[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

/** Data e hora no formato DOS (16 bits cada) que o cabeçalho ZIP exige. */
function dataHoraDos(mtimeMs) {
  const data = new Date(mtimeMs);
  const dosHora = (data.getHours() << 11) | (data.getMinutes() << 5) | Math.floor(data.getSeconds() / 2);
  const dosData = ((data.getFullYear() - 1980) << 9) | ((data.getMonth() + 1) << 5) | data.getDate();
  return { dosHora, dosData };
}

/** Caminhos absolutos de todo arquivo sob `diretorio`, recursivamente. */
function listarArquivos(diretorio) {
  const encontrados = [];
  for (const entrada of fs.readdirSync(diretorio, { withFileTypes: true })) {
    const caminho = path.join(diretorio, entrada.name);
    if (entrada.isDirectory()) {
      encontrados.push(...listarArquivos(caminho));
    } else if (entrada.isFile()) {
      encontrados.push(caminho);
    }
  }
  return encontrados;
}

function cabecalhoLocal({ nomeBuffer, comprimido, crc, tamanhoOriginal, dosHora, dosData }) {
  const cabecalho = Buffer.alloc(30);
  cabecalho.writeUInt32LE(ASSINATURA_LOCAL, 0);
  cabecalho.writeUInt16LE(20, 4); // versão mínima para extrair
  cabecalho.writeUInt16LE(0, 6); // flags
  cabecalho.writeUInt16LE(METODO_DEFLATE, 8);
  cabecalho.writeUInt16LE(dosHora, 10);
  cabecalho.writeUInt16LE(dosData, 12);
  cabecalho.writeUInt32LE(crc, 14);
  cabecalho.writeUInt32LE(comprimido.length, 18);
  cabecalho.writeUInt32LE(tamanhoOriginal, 22);
  cabecalho.writeUInt16LE(nomeBuffer.length, 26);
  cabecalho.writeUInt16LE(0, 28); // sem campo extra
  return Buffer.concat([cabecalho, nomeBuffer]);
}

function cabecalhoCentral({ nomeBuffer, comprimido, crc, tamanhoOriginal, dosHora, dosData, offsetLocal }) {
  const cabecalho = Buffer.alloc(46);
  cabecalho.writeUInt32LE(ASSINATURA_CENTRAL, 0);
  cabecalho.writeUInt16LE(20, 4); // versão que gerou
  cabecalho.writeUInt16LE(20, 6); // versão mínima para extrair
  cabecalho.writeUInt16LE(0, 8); // flags
  cabecalho.writeUInt16LE(METODO_DEFLATE, 10);
  cabecalho.writeUInt16LE(dosHora, 12);
  cabecalho.writeUInt16LE(dosData, 14);
  cabecalho.writeUInt32LE(crc, 16);
  cabecalho.writeUInt32LE(comprimido.length, 20);
  cabecalho.writeUInt32LE(tamanhoOriginal, 24);
  cabecalho.writeUInt16LE(nomeBuffer.length, 28);
  cabecalho.writeUInt16LE(0, 30); // campo extra
  cabecalho.writeUInt16LE(0, 32); // comentário
  cabecalho.writeUInt16LE(0, 34); // disco inicial
  cabecalho.writeUInt16LE(0, 36); // atributos internos
  cabecalho.writeUInt32LE((0o100644 << 16) >>> 0, 38); // atributos externos (permissão unix)
  cabecalho.writeUInt32LE(offsetLocal, 42);
  return Buffer.concat([cabecalho, nomeBuffer]);
}

function fimDiretorioCentral(quantidade, tamanhoCentral, offsetCentral) {
  const cabecalho = Buffer.alloc(22);
  cabecalho.writeUInt32LE(ASSINATURA_FIM, 0);
  cabecalho.writeUInt16LE(0, 4); // número deste disco
  cabecalho.writeUInt16LE(0, 6); // disco do início do diretório central
  cabecalho.writeUInt16LE(quantidade, 8);
  cabecalho.writeUInt16LE(quantidade, 10);
  cabecalho.writeUInt32LE(tamanhoCentral, 12);
  cabecalho.writeUInt32LE(offsetCentral, 16);
  cabecalho.writeUInt16LE(0, 20); // comentário
  return cabecalho;
}

/** Monta o .zip de `data/` em memória — o volume é de dezenas/poucas centenas de KB. */
export function criarBackupZip() {
  const raiz = dataDir();
  const partes = [];
  const centrais = [];
  let offset = 0;

  for (const caminho of listarArquivos(raiz)) {
    const relativo = path.relative(raiz, caminho).split(path.sep).join("/");
    if (ARQUIVOS_EXCLUIDOS.has(relativo) || NOMES_EXCLUIDOS.has(path.basename(caminho))) continue;

    const original = fs.readFileSync(caminho);
    const comprimido = zlib.deflateRawSync(original);
    const crc = crc32(original);
    const { mtimeMs } = fs.statSync(caminho);
    const { dosHora, dosData } = dataHoraDos(mtimeMs);
    const nomeBuffer = Buffer.from(relativo, "utf8");
    const dados = { nomeBuffer, comprimido, crc, tamanhoOriginal: original.length, dosHora, dosData };

    const local = cabecalhoLocal(dados);
    partes.push(local, comprimido);
    centrais.push(cabecalhoCentral({ ...dados, offsetLocal: offset }));
    offset += local.length + comprimido.length;
  }

  const diretorioCentral = Buffer.concat(centrais);
  const fim = fimDiretorioCentral(centrais.length, diretorioCentral.length, offset);
  return Buffer.concat([...partes, diretorioCentral, fim]);
}

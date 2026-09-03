/**
 * Persistência e validação da carteira em arquivo JSON.
 *
 * Tipos de posição suportados:
 *   - "fii" / "acao": ticker, quantidade, preço médio
 *   - "cdb"         : banco, valor inicial, indexador, taxa, datas e a
 *                     forma de pagamento dos juros (no vencimento ou mensal)
 */

import fs from "node:fs";
import crypto from "node:crypto";

import { garantirDiretorios, portfolioFile } from "../config/paths.js";
import { agoraISO, paraData, paraISO } from "../util/datas.js";

export const VERSAO = 2;

export const TIPOS_VARIAVEL = ["fii", "acao"];
export const TIPOS_RENDA_FIXA = ["cdb"];
export const TIPOS = [...TIPOS_VARIAVEL, ...TIPOS_RENDA_FIXA];

export const INDEXADORES = ["CDI", "PRE", "IPCA"];
export const PAGAMENTOS_JUROS = ["vencimento", "mensal"];

export const CONFIG_PADRAO = Object.freeze({
  max_fatos: 6,
  max_oportunidades: 4,
  limite_fgc: 250000.0,
  alerta_vencimento_dias: 60,
  alerta_concentracao_pct: 25.0,
  alerta_prejuizo_pct: 15.0,
});

/** Erro de validação de uma posição da carteira. */
export class ValidacaoError extends Error {
  constructor(mensagem) {
    super(mensagem);
    this.name = "ValidacaoError";
  }
}

// ─────────────────────────────────────────────
// Leitura / escrita
// ─────────────────────────────────────────────

export function carteiraVazia() {
  return { versao: VERSAO, perfil: "", posicoes: [], config: { ...CONFIG_PADRAO } };
}

/** Carrega a carteira, migrando formatos antigos quando necessário. */
export function load() {
  const arquivo = portfolioFile();
  if (!fs.existsSync(arquivo)) {
    const carteira = carteiraVazia();
    save(carteira);
    return carteira;
  }

  let dados;
  try {
    dados = JSON.parse(fs.readFileSync(arquivo, "utf8"));
  } catch (erro) {
    throw new Error(`Carteira corrompida em ${arquivo}: ${erro.message}`);
  }

  if (dados.versao !== VERSAO) {
    dados = migrar(dados);
    save(dados);
  }

  dados.config = { ...CONFIG_PADRAO, ...(dados.config || {}) };
  dados.perfil = dados.perfil ?? "";
  dados.posicoes = dados.posicoes ?? [];
  return dados;
}

export function save(carteira) {
  garantirDiretorios();
  carteira.versao = VERSAO;
  carteira.atualizado_em = agoraISO();

  const destino = portfolioFile();
  const temporario = `${destino}.tmp`;
  fs.writeFileSync(temporario, JSON.stringify(carteira, null, 2), "utf8");
  fs.renameSync(temporario, destino);
}

/** Converte o formato v1 (lista de tickers de FII) para o formato atual. */
export function migrar(antigo) {
  const nova = carteiraVazia();
  nova.perfil = antigo.profile || antigo.perfil || "";

  for (const pos of antigo.posicoes || []) {
    try {
      nova.posicoes.push(normalizar(pos));
    } catch (erro) {
      if (!(erro instanceof ValidacaoError)) throw erro;
    }
  }

  for (const ticker of antigo.tickers || []) {
    nova.posicoes.push(
      normalizar({
        tipo: "fii",
        ticker,
        quantidade: 0,
        preco_medio: 0,
        observacao: "Migrado do formato antigo - informe quantidade e preco medio.",
      }),
    );
  }

  for (const chave of ["max_fatos", "max_oportunidades"]) {
    if (chave in antigo) nova.config[chave] = antigo[chave];
  }

  return nova;
}

// ─────────────────────────────────────────────
// Validação / normalização
// ─────────────────────────────────────────────

function numero(valor, campo, { minimo = null } = {}) {
  if (valor === null || valor === undefined || valor === "") {
    throw new ValidacaoError(`Campo '${campo}' e obrigatorio.`);
  }
  const n = Number(String(valor).replace(",", "."));
  if (!Number.isFinite(n)) {
    throw new ValidacaoError(`Campo '${campo}' deve ser numerico.`);
  }
  if (minimo !== null && n < minimo) {
    throw new ValidacaoError(`Campo '${campo}' deve ser >= ${minimo}.`);
  }
  return n;
}

function data(valor, campo, { obrigatorio = true } = {}) {
  if (!valor) {
    if (obrigatorio) {
      throw new ValidacaoError(`Campo '${campo}' e obrigatorio (formato AAAA-MM-DD).`);
    }
    return null;
  }
  try {
    return paraISO(paraData(valor));
  } catch {
    throw new ValidacaoError(`Campo '${campo}' invalido - use AAAA-MM-DD.`);
  }
}

function texto(valor, campo, { obrigatorio = true } = {}) {
  const txt = valor === null || valor === undefined ? "" : String(valor).trim();
  if (obrigatorio && !txt) throw new ValidacaoError(`Campo '${campo}' e obrigatorio.`);
  return txt;
}

function novoId() {
  return crypto.randomUUID().replace(/-/g, "").slice(0, 12);
}

/** Valida e normaliza uma posição, devolvendo um objeto pronto para gravar. */
export function normalizar(pos) {
  const tipo = texto(pos.tipo, "tipo").toLowerCase();
  if (!TIPOS.includes(tipo)) {
    throw new ValidacaoError(`Tipo invalido: '${tipo}'. Use: ${TIPOS.join(", ")}.`);
  }

  const base = {
    id: pos.id || novoId(),
    tipo,
    observacao: texto(pos.observacao, "observacao", { obrigatorio: false }),
  };

  if (TIPOS_VARIAVEL.includes(tipo)) {
    return {
      ...base,
      ticker: texto(pos.ticker, "ticker").toUpperCase().replace(".SA", ""),
      quantidade: numero(pos.quantidade, "quantidade", { minimo: 0 }),
      preco_medio: numero(pos.preco_medio, "preco_medio", { minimo: 0 }),
      data_compra: data(pos.data_compra, "data_compra", { obrigatorio: false }),
    };
  }

  // CDB
  const indexador = texto(pos.indexador || "CDI", "indexador").toUpperCase();
  if (!INDEXADORES.includes(indexador)) {
    throw new ValidacaoError(
      `Indexador invalido: '${indexador}'. Use: ${INDEXADORES.join(", ")}.`,
    );
  }

  const dataAplicacao = data(pos.data_aplicacao, "data_aplicacao");
  const dataVencimento = data(pos.data_vencimento, "data_vencimento");
  if (dataVencimento < dataAplicacao) {
    throw new ValidacaoError("Data de vencimento anterior a data de aplicacao.");
  }

  const pagamentoJuros = texto(
    pos.pagamento_juros || "vencimento",
    "pagamento_juros",
  ).toLowerCase();
  if (!PAGAMENTOS_JUROS.includes(pagamentoJuros)) {
    throw new ValidacaoError(
      `Pagamento de juros invalido: '${pagamentoJuros}'. Use: ${PAGAMENTOS_JUROS.join(", ")}.`,
    );
  }

  const cdb = {
    ...base,
    banco: texto(pos.banco, "banco"),
    nome: texto(pos.nome, "nome", { obrigatorio: false }),
    valor_inicial: numero(pos.valor_inicial, "valor_inicial", { minimo: 0.01 }),
    indexador,
    taxa: numero(pos.taxa, "taxa", { minimo: 0 }),
    data_aplicacao: dataAplicacao,
    data_vencimento: dataVencimento,
    pagamento_juros: pagamentoJuros,
    liquidez_diaria: Boolean(pos.liquidez_diaria),
  };
  if (!cdb.nome) cdb.nome = `CDB ${cdb.banco} ${rotuloTaxa(cdb)}`;
  return cdb;
}

/** Descrição legível da remuneração de um CDB. */
export function rotuloTaxa(cdb) {
  const taxa = String(Number(cdb.taxa));
  if (cdb.indexador === "CDI") return `${taxa}% do CDI`;
  if (cdb.indexador === "PRE") return `${taxa}% a.a.`;
  return `IPCA + ${taxa}% a.a.`;
}

/** Nome curto de exibição da posição. */
export function descricao(pos) {
  if (TIPOS_VARIAVEL.includes(pos.tipo)) return pos.ticker;
  return pos.nome || `CDB ${pos.banco || ""}`;
}

// ─────────────────────────────────────────────
// CRUD
// ─────────────────────────────────────────────

export function adicionar(pos) {
  const carteira = load();
  const nova = normalizar({ ...pos, id: null });
  carteira.posicoes.push(nova);
  save(carteira);
  return nova;
}

export function atualizar(posId, pos) {
  const carteira = load();
  const indice = carteira.posicoes.findIndex((p) => p.id === posId);
  if (indice === -1) throw new ValidacaoError(`Posicao '${posId}' nao encontrada.`);
  const nova = normalizar({ ...pos, id: posId });
  carteira.posicoes[indice] = nova;
  save(carteira);
  return nova;
}

export function remover(posId) {
  const carteira = load();
  const restantes = carteira.posicoes.filter((p) => p.id !== posId);
  if (restantes.length === carteira.posicoes.length) {
    throw new ValidacaoError(`Posicao '${posId}' nao encontrada.`);
  }
  carteira.posicoes = restantes;
  save(carteira);
}

export function atualizarConfig(patch) {
  const carteira = load();
  if ("perfil" in patch) {
    carteira.perfil = texto(patch.perfil, "perfil", { obrigatorio: false });
  }
  for (const [chave, valor] of Object.entries(patch.config || {})) {
    if (chave in CONFIG_PADRAO) {
      carteira.config[chave] = numero(valor, chave, { minimo: 0 });
    }
  }
  save(carteira);
  return carteira;
}

/** Tickers únicos de renda variável presentes na carteira. */
export function tickers(carteira) {
  const vistos = [];
  for (const p of carteira.posicoes) {
    if (TIPOS_VARIAVEL.includes(p.tipo) && !vistos.includes(p.ticker)) {
      vistos.push(p.ticker);
    }
  }
  return vistos;
}

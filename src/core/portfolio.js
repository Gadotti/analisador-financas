/**
 * Persistência e validação da carteira em arquivo JSON.
 *
 * Tipos de posição suportados:
 *   - "fii" / "acao"      : ticker, quantidade, preço médio
 *   - "cdb" / "lci" / "lca": banco emissor, valor aplicado, indexador, taxa e prazo
 *   - "tesouro"           : título do Tesouro Direto, com os mesmos campos de prazo
 *
 * As regras dos tipos de renda fixa moram em `rendaFixa.js`; aqui ficam só a
 * leitura, a gravação e o CRUD do arquivo.
 */

import fs from "node:fs";
import crypto from "node:crypto";

import { garantirDiretorios, portfolioFile } from "../config/paths.js";
import { agoraISO } from "../util/datas.js";
import * as rendaFixa from "./rendaFixa.js";
import {
  ValidacaoError,
  booleano,
  data,
  listaDeInteiros,
  numero,
  opcao,
  texto,
} from "./validacao.js";

export { ValidacaoError } from "./validacao.js";
export { EMISSOR_TESOURO, emissorDe, nomeTesouro, rotuloTaxa } from "./rendaFixa.js";

export const VERSAO = 2;

export const TIPOS_VARIAVEL = ["fii", "acao"];
export const TIPOS_RENDA_FIXA = rendaFixa.TIPOS_RENDA_FIXA;
export const TIPOS_BANCARIOS = rendaFixa.TIPOS_BANCARIOS;
export const TIPOS = [...TIPOS_VARIAVEL, ...TIPOS_RENDA_FIXA];

export const INDEXADORES_BANCARIO = rendaFixa.INDEXADORES_BANCARIO;
export const INDEXADORES_TESOURO = rendaFixa.INDEXADORES_TESOURO;
export const PAGAMENTOS_CDB = rendaFixa.PAGAMENTOS_CDB;
export const PAGAMENTOS_LETRA = rendaFixa.PAGAMENTOS_LETRA;
export const PAGAMENTOS_TESOURO = rendaFixa.PAGAMENTOS_TESOURO;

/**
 * Mensagem curta do Telegram — espelho de `analise.portfolio.TELEGRAM_PADRAO`.
 *
 * Quem lê e aplica estes limiares é o Python (`analise.relevancia`); aqui eles
 * existem para serem validados e gravados. Cada bloco tem um interruptor
 * (`ativo` — pode aparecer?) e um limiar (merece aparecer HOJE?), e é o limiar
 * que faz a mensagem variar de um dia para o outro sem nada memorizado.
 *
 * `dias_semana` segue o `weekday()` do Python: 0 = segunda, 6 = domingo.
 */
export const TELEGRAM_PADRAO = Object.freeze({
  max_itens: 6,
  so_se_relevante: false,
  silencioso_sem_alerta: true,
  variacao_dia: { ativo: true, limiar_pct: 0.5 },
  macro: { ativo: true, limiar_pp: 0.01 },
  movimento: { ativo: true, limiar_pct: 3.0, peso_minimo_pct: 3.0, max: 3 },
  calendario_rf: { ativo: true, marcos_dias: [30, 15, 7, 3, 1], max: 2 },
  alertas: { ativo: true, severidade_minima: "atencao", max: 3 },
  fatos_ia: { ativo: true, severidade_minima: "atencao", peso_minimo_pct: 5.0, max: 3 },
  riscos_ia: { ativo: true, severidade_minima: "alerta", max: 2 },
  indicadores: { ativo: true, p_vp_minimo: 0.85, p_vp_maximo: 1.15, dy_minimo_pct: 8.0 },
  aprofundamento: { ativo: true, por_dia: 1 },
  resumo_ia: { ativo: true, dias_semana: [4] },
  semanal: { ativo: true, dia_semana: 4 },
});

export const SEVERIDADES = ["info", "atencao", "alerta"];

export const CONFIG_PADRAO = Object.freeze({
  max_fatos: 6,
  max_oportunidades: 4,
  max_execucoes: 30,
  limite_fgc: 250000.0,
  alerta_vencimento_dias: 60,
  alerta_concentracao_pct: 25.0,
  alerta_prejuizo_pct: 15.0,
  telegram: TELEGRAM_PADRAO,
});

// Piso por chave; as demais aceitam zero. Um teto de log em zero apagaria o
// log de execuções inteiro na rodada seguinte.
const MINIMO_CONFIG = { max_execucoes: 1 };

// Teto por chave do bloco do Telegram. O dia da semana é o único com limite
// superior — 6 é domingo, e 7 não existe.
const MAXIMO_TELEGRAM = { dia_semana: 6, dias_semana: 6 };

/** Cópia independente dos padrões: `CONFIG_PADRAO` tem um nível aninhado. */
export function configPadrao() {
  return { ...CONFIG_PADRAO, telegram: structuredClone(TELEGRAM_PADRAO) };
}

/**
 * Bloco `telegram` gravado em disco sobre os padrões, um nível abaixo também.
 *
 * Um espalhamento raso trocaria o padrão inteiro pelo bloco parcial do
 * arquivo, e um cadastro gravado antes de um limiar novo existir perderia esse
 * limiar. Espelha `analise.portfolio.telegram_do_cadastro`.
 */
export function telegramDoCadastro(bruto) {
  const completo = structuredClone(TELEGRAM_PADRAO);
  for (const [chave, valor] of Object.entries(bruto || {})) {
    const padrao = completo[chave];
    if (ehBloco(padrao) && ehBloco(valor)) {
      Object.assign(completo[chave], valor);
    } else {
      completo[chave] = valor;
    }
  }
  return completo;
}

const ehBloco = (valor) =>
  typeof valor === "object" && valor !== null && !Array.isArray(valor);

/**
 * Converte um campo do bloco `telegram` usando o próprio padrão como molde.
 *
 * O tipo sai de `TELEGRAM_PADRAO`: padrão booleano exige booleano, numérico
 * exige número, lista exige lista de inteiros. Não existe uma segunda tabela
 * de tipos para divergir da primeira.
 */
function campoTelegram(bruto, padrao, campo, chave) {
  const maximo = MAXIMO_TELEGRAM[chave] ?? null;
  if (typeof padrao === "boolean") return booleano(bruto, campo);
  if (typeof padrao === "number") return numero(bruto, campo, { minimo: 0, maximo });
  if (Array.isArray(padrao)) return listaDeInteiros(bruto, campo, { maximo });
  return opcao(bruto, campo, SEVERIDADES, { rotulo: `Campo '${campo}'` });
}

/** Aplica um patch parcial ao bloco `telegram`, validando campo a campo. */
function telegramComPatch(atual, patch) {
  const saida = telegramDoCadastro(atual);
  for (const [chave, valor] of Object.entries(patch || {})) {
    const padrao = TELEGRAM_PADRAO[chave];
    if (padrao === undefined) continue;

    if (!ehBloco(padrao)) {
      saida[chave] = campoTelegram(valor, padrao, `telegram.${chave}`, chave);
      continue;
    }
    for (const [sub, valorSub] of Object.entries(valor || {})) {
      if (padrao[sub] === undefined) continue;
      saida[chave][sub] = campoTelegram(
        valorSub, padrao[sub], `telegram.${chave}.${sub}`, sub,
      );
    }
  }
  return saida;
}

// ─────────────────────────────────────────────
// Leitura / escrita
// ─────────────────────────────────────────────

export function carteiraVazia() {
  return { versao: VERSAO, perfil: "", posicoes: [], config: configPadrao() };
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

  dados.config = { ...configPadrao(), ...(dados.config || {}) };
  dados.config.telegram = telegramDoCadastro((dados.config || {}).telegram);
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

  return rendaFixa.normalizar(tipo, pos, base);
}

/** Nome curto de exibição da posição. */
export function descricao(pos) {
  if (TIPOS_VARIAVEL.includes(pos.tipo)) return pos.ticker;
  return rendaFixa.descricao(pos);
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
    if (chave === "telegram") {
      carteira.config.telegram = telegramComPatch(carteira.config.telegram, valor);
    } else if (chave in CONFIG_PADRAO) {
      carteira.config[chave] = numero(valor, chave, { minimo: MINIMO_CONFIG[chave] ?? 0 });
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

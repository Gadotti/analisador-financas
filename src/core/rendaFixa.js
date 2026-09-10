/**
 * Regras de cadastro da renda fixa: papel bancário (CDB, LCI e LCA) e títulos
 * do Tesouro Direto.
 *
 * Todos compartilham o esqueleto (valor aplicado, indexador, taxa, prazo e
 * forma de pagamento dos juros) e divergem no que a tabela `REGRAS` declara:
 *
 *   - o indexador disponível (o papel bancário acompanha o CDI; o Tesouro, a
 *     Selic);
 *   - a periodicidade do cupom oferecida;
 *   - quem é o emissor (um banco, com teto do FGC; ou o Tesouro Nacional);
 *   - de onde vem a taxa: a do papel bancário está no contrato e é digitada; a
 *     do título público é a do pregão em que ele foi comprado, e a análise a
 *     busca no Tesouro Transparente — por isso ela é opcional aqui.
 *
 * O que não está aqui é o regime de liquidação — quem paga IR e quem paga
 * custódia à B3 mora em `analise/fixed_income.REGIME`, junto do cálculo. A
 * isenção de IR da LCI e da LCA não muda nada no cadastro.
 */

import { ValidacaoError, data, numero, opcao, texto } from "./validacao.js";

export const INDEXADORES_BANCARIO = ["CDI", "PRE", "IPCA"];
export const INDEXADORES_TESOURO = ["SELIC", "PRE", "IPCA"];

export const PAGAMENTOS_CDB = ["vencimento", "mensal"];
// A letra de crédito é ofertada com cupom mensal e semestral, além do
// pagamento único no vencimento.
export const PAGAMENTOS_LETRA = ["vencimento", "mensal", "semestral"];
export const PAGAMENTOS_TESOURO = ["vencimento", "semestral"];

export const EMISSOR_TESOURO = "Tesouro Nacional";

/**
 * CDB, LCI e LCA são o mesmo papel do ponto de vista do cadastro: um banco
 * emissor, uma taxa contratada e um prazo. O que os separa é a sigla que
 * nomeia a posição e a periodicidade de cupom que cada um oferece.
 *
 * A carência legal da LCI e da LCA é o motivo de a interface não oferecer a
 * elas a caixa de liquidez diária — como já não a oferece ao Tesouro.
 */
function papelBancario(sigla, pagamentos) {
  return {
    indexadores: INDEXADORES_BANCARIO,
    pagamentos,
    taxaObrigatoria: true,
    campos: (pos) => ({ banco: texto(pos.banco, "banco") }),
    emissor: (pos) => pos.banco,
    semNome: (pos) => `${sigla} ${pos.banco || ""}`.trim(),
    nomePadrao: (titulo) => `${sigla} ${titulo.banco} ${rotuloTaxa(titulo)}`,
  };
}

const REGRAS = {
  cdb: papelBancario("CDB", PAGAMENTOS_CDB),
  lci: papelBancario("LCI", PAGAMENTOS_LETRA),
  lca: papelBancario("LCA", PAGAMENTOS_LETRA),
  tesouro: {
    indexadores: INDEXADORES_TESOURO,
    pagamentos: PAGAMENTOS_TESOURO,
    // Em branco, a taxa é buscada no pregão da compra. Se o extrato da
    // corretora trouxer a taxa, informá-la aqui prevalece sobre a busca.
    taxaObrigatoria: false,
    campos: () => ({}),
    emissor: () => EMISSOR_TESOURO,
    semNome: () => "Tesouro Direto",
    nomePadrao: (titulo) => nomeTesouro(titulo),
    conferir: (titulo) => {
      if (titulo.indexador === "SELIC" && titulo.pagamento_juros !== "vencimento") {
        throw new ValidacaoError(
          `Tesouro Selic paga tudo no vencimento: pagamento_juros e '${titulo.pagamento_juros}', ` +
            "mas so aceita 'vencimento'.",
        );
      }
    },
  },
};

/** Papéis emitidos por banco: têm emissor no cadastro e consomem teto do FGC. */
export const TIPOS_BANCARIOS = ["cdb", "lci", "lca"];

export const TIPOS_RENDA_FIXA = Object.keys(REGRAS);

/** Descrição legível da remuneração de um título de renda fixa. */
export function rotuloTaxa(titulo) {
  if (titulo.taxa === null || titulo.taxa === undefined) return "taxa a buscar";
  const taxa = String(Number(titulo.taxa));
  if (titulo.indexador === "CDI") return `${taxa}% do CDI`;
  if (titulo.indexador === "SELIC") return `SELIC + ${taxa}% a.a.`;
  if (titulo.indexador === "PRE") return `${taxa}% a.a.`;
  return `IPCA + ${taxa}% a.a.`;
}

/** Nome comercial do papel, no padrão em que o Tesouro Direto o publica. */
export function nomeTesouro(titulo) {
  const familia = { SELIC: "Tesouro Selic", PRE: "Tesouro Prefixado", IPCA: "Tesouro IPCA+" };
  const ano = String(titulo.data_vencimento).slice(0, 4);
  const cupom = titulo.pagamento_juros === "semestral" ? " com Juros Semestrais" : "";
  return `${familia[titulo.indexador]} ${ano}${cupom}`;
}

function prazo(pos) {
  const aplicacao = data(pos.data_aplicacao, "data_aplicacao");
  const vencimento = data(pos.data_vencimento, "data_vencimento");
  if (vencimento < aplicacao) {
    throw new ValidacaoError(
      `Data de vencimento (${vencimento}) anterior a data de aplicacao (${aplicacao}).`,
    );
  }
  return { data_aplicacao: aplicacao, data_vencimento: vencimento };
}

/**
 * Valida e normaliza um título de renda fixa.
 *
 * @param {string} tipo Uma das chaves de `REGRAS`.
 * @param {object} pos Dados crus vindos do formulário ou da API.
 * @param {object} base Campos comuns a qualquer posição (id, tipo, observação).
 */
export function normalizar(tipo, pos, base) {
  const regra = REGRAS[tipo];
  const titulo = {
    ...base,
    ...regra.campos(pos),
    nome: texto(pos.nome, "nome", { obrigatorio: false }),
    valor_inicial: numero(pos.valor_inicial, "valor_inicial", { minimo: 0.01 }),
    indexador: opcao(pos.indexador || regra.indexadores[0], "indexador", regra.indexadores, {
      rotulo: "Indexador",
      ajustar: (v) => v.toUpperCase(),
    }),
    taxa: numero(pos.taxa, "taxa", { minimo: 0, obrigatorio: regra.taxaObrigatoria }),
    ...prazo(pos),
    pagamento_juros: opcao(
      pos.pagamento_juros || "vencimento",
      "pagamento_juros",
      regra.pagamentos,
      { rotulo: "Pagamento de juros", ajustar: (v) => v.toLowerCase() },
    ),
    liquidez_diaria: Boolean(pos.liquidez_diaria),
  };
  regra.conferir?.(titulo);
  if (!titulo.nome) titulo.nome = regra.nomePadrao(titulo);
  return titulo;
}

/** Quem responde pelo título: o banco emissor ou o Tesouro Nacional. */
export const emissorDe = (titulo) => REGRAS[titulo.tipo].emissor(titulo);

/** Nome de exibição, com um rótulo genérico quando o título não tem nome. */
export const descricao = (titulo) => titulo.nome || REGRAS[titulo.tipo].semNome(titulo);

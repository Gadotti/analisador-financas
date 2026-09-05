/**
 * Regras de cadastro da renda fixa: CDB e títulos do Tesouro Direto.
 *
 * Os dois compartilham o esqueleto (valor aplicado, indexador, taxa, prazo e
 * forma de pagamento dos juros) e divergem em três pontos, declarados na
 * tabela `REGRAS`:
 *
 *   - o indexador disponível (CDB acompanha o CDI; o Tesouro, a Selic);
 *   - a periodicidade do cupom (CDB paga mensal; o Tesouro, semestral);
 *   - quem é o emissor (um banco, com teto do FGC; ou o Tesouro Nacional);
 *   - de onde vem a taxa: a do CDB está no contrato e é digitada; a do título
 *     público é a do pregão em que ele foi comprado, e a análise a busca no
 *     Tesouro Transparente — por isso ela é opcional aqui.
 */

import { ValidacaoError, data, numero, opcao, texto } from "./validacao.js";

export const INDEXADORES_CDB = ["CDI", "PRE", "IPCA"];
export const INDEXADORES_TESOURO = ["SELIC", "PRE", "IPCA"];

export const PAGAMENTOS_CDB = ["vencimento", "mensal"];
export const PAGAMENTOS_TESOURO = ["vencimento", "semestral"];

export const EMISSOR_TESOURO = "Tesouro Nacional";

const REGRAS = {
  cdb: {
    indexadores: INDEXADORES_CDB,
    pagamentos: PAGAMENTOS_CDB,
    taxaObrigatoria: true,
    campos: (pos) => ({ banco: texto(pos.banco, "banco") }),
    emissor: (pos) => pos.banco,
    semNome: (pos) => `CDB ${pos.banco || ""}`.trim(),
  },
  tesouro: {
    indexadores: INDEXADORES_TESOURO,
    pagamentos: PAGAMENTOS_TESOURO,
    // Em branco, a taxa é buscada no pregão da compra. Se o extrato da
    // corretora trouxer a taxa, informá-la aqui prevalece sobre a busca.
    taxaObrigatoria: false,
    campos: () => ({}),
    emissor: () => EMISSOR_TESOURO,
    semNome: () => "Tesouro Direto",
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

/** Nome de exibição de um título, gerado quando o usuário não informa um. */
function nomePadrao(titulo) {
  if (titulo.tipo === "tesouro") return nomeTesouro(titulo);
  return `CDB ${titulo.banco} ${rotuloTaxa(titulo)}`;
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
 * @param {string} tipo "cdb" ou "tesouro".
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
  if (!titulo.nome) titulo.nome = nomePadrao(titulo);
  return titulo;
}

/** Quem responde pelo título: o banco emissor ou o Tesouro Nacional. */
export const emissorDe = (titulo) => REGRAS[titulo.tipo].emissor(titulo);

/** Nome de exibição, com um rótulo genérico quando o título não tem nome. */
export const descricao = (titulo) => titulo.nome || REGRAS[titulo.tipo].semNome(titulo);

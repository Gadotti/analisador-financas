/**
 * Listagem de posições — uma tabela agrupada por classe de ativo.
 *
 * Cada classe declara as suas próprias colunas, porque não têm o mesmo
 * assunto: um CDB não tem P/VP e um FII não tem vencimento. Mas todas
 * terminam nas mesmas quatro — valor, resultado, peso e ações — e por isso a
 * tabela continua sendo uma só: os números ficam alinhados de ponta a ponta e
 * cada grupo ganha o seu cabeçalho e o seu subtotal.
 *
 * Busca, ordenação e recolhimento são estado desta tela, guardado aqui.
 */

import { $, classeSinal, dataBR, esc, moeda, mostrar, num, pct } from "./formato.js";
import { icone } from "./icones.js";

const ROTULO_TIPO = { fii: "FII", acao: "AÇÃO", cdb: "CDB", tesouro: "TESOURO" };

const CUPOM_ROTULO = { mensal: "juros mensais", semestral: "juros semestrais" };

const estado = {
  dados: { posicoes: [] },
  acoes: null,
  termo: "",
  ordem: "valor",
  recolhidos: new Set(),
  escalaPeso: 1,
};

/** Coluna de identificação: o banco nomeia o CDB; o Tesouro, o próprio papel. */
const nomeDaLinha = (posicao) =>
  ({ cdb: posicao.banco, tesouro: posicao.nome })[posicao.tipo] || posicao.ticker;

/** Chave de comparação para busca e ordenação: sem acento e em minúsculas. */
const semAcento = (texto) =>
  String(texto ?? "")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();

const indexar = (itens, chave) =>
  Object.fromEntries((itens || []).map((item) => [item[chave], item]));

// ── Peças de uma célula ────────────────────

/** O dado principal da célula e as linhas de apoio que ficam abaixo dele. */
const celula = (principal, ...apoios) =>
  principal + apoios.filter(Boolean).map((t) => `<div class="apoio">${t}</div>`).join("");

const observacaoDe = (posicao) => posicao.observacao && esc(posicao.observacao);

const erroDe = (calculada) =>
  calculada?.erro_cotacao && '<span class="neg">cotação indisponível</span>';

/** Quanto falta para o vencimento — ou o aviso de que ele já passou. */
function prazo(calculada) {
  if (!calculada) return "";
  return calculada.vencido
    ? '<strong class="neg">vencido</strong>'
    : `faltam ${calculada.dias_para_vencer} dias`;
}

/** Periodicidade do cupom e a data do próximo pagamento, quando existe. */
function cupom(posicao, calculada) {
  const rotulo = CUPOM_ROTULO[posicao.pagamento_juros];
  if (!rotulo) return "";
  if (!calculada) return rotulo;
  return calculada.proximo_pagamento
    ? `${rotulo} · próximo em ${dataBR(calculada.proximo_pagamento)}`
    : `${rotulo} · sem novos pagamentos`;
}

/** Cupons já sacados: saíram da carteira, então não estão em `valor_atual`. */
const jurosRecebidos = (calculada) =>
  calculada.pagamentos_realizados
    ? `+ ${moeda(calculada.juros_recebidos_liquido)} em cupons`
    : "";

/** Valor e percentual do resultado, os dois na cor do sinal. */
function textoResultado(valor, percentual) {
  const sinal = classeSinal(valor);
  return `<span class="${sinal}">${moeda(valor)}</span>
    <div class="apoio ${sinal}">${pct(percentual)}</div>`;
}

// ── Colunas de cada classe de ativo ────────

const COLUNAS_VARIAVEL = [
  {
    rotulo: "Ativo",
    celula: ({ posicao, calculada, ficha }) =>
      celula(
        `<strong>${esc(posicao.ticker)}</strong>`,
        ficha?.nome && esc(ficha.nome),
        observacaoDe(posicao),
        erroDe(calculada)
      ),
  },
  {
    rotulo: "Segmento",
    celula: ({ ficha }) =>
      celula(esc(ficha?.segmento || "—"), ficha?.gestora && esc(ficha.gestora)),
  },
  {
    rotulo: "Posição",
    num: true,
    celula: ({ posicao, calculada }) =>
      celula(
        calculada?.preco_atual
          ? `${posicao.quantidade} × ${moeda(calculada.preco_atual)}`
          : `${posicao.quantidade} cotas`,
        `PM ${moeda(posicao.preco_medio)}`
      ),
  },
  {
    rotulo: "P/VP",
    num: true,
    mono: true,
    celula: ({ ficha }) => (ficha?.p_vp ? num(ficha.p_vp, 2) : "—"),
  },
  {
    rotulo: "DY 12M",
    num: true,
    mono: true,
    celula: ({ ficha }) => (ficha?.dy_12m_pct ? pct(ficha.dy_12m_pct, 1, false) : "—"),
  },
];

const COLUNA_VENCIMENTO = {
  rotulo: "Vencimento",
  celula: ({ posicao, calculada }) =>
    celula(dataBR(posicao.data_vencimento), prazo(calculada), cupom(posicao, calculada)),
};

const COLUNA_LIQUIDO = {
  rotulo: "Líquido hoje",
  num: true,
  mono: true,
  celula: ({ calculada }) =>
    calculada ? celula(moeda(calculada.valor_liquido), jurosRecebidos(calculada)) : "—",
};

const COLUNAS_CDB = [
  {
    rotulo: "Emissor",
    celula: ({ posicao, calculada }) =>
      celula(
        `<strong>${esc(posicao.banco)}</strong>`,
        observacaoDe(posicao),
        erroDe(calculada)
      ),
  },
  {
    rotulo: "Remuneração",
    celula: ({ posicao, calculada }) =>
      celula(
        esc(calculada?.rotulo_taxa || "—"),
        posicao.liquidez_diaria ? "liquidez diária" : ""
      ),
  },
  COLUNA_VENCIMENTO,
  {
    rotulo: "Aplicado",
    num: true,
    mono: true,
    celula: ({ posicao }) =>
      celula(moeda(posicao.valor_inicial), `em ${dataBR(posicao.data_aplicacao)}`),
  },
  COLUNA_LIQUIDO,
];

/** De onde saiu a taxa travada na compra — o cadastro vence o pregão. */
const origemDaTaxa = (calculada) =>
  ({ cadastro: "taxa informada", tesouro_transparente: "taxa do pregão da compra" })[
    calculada?.taxa_origem
  ] || "";

const COLUNAS_TESOURO = [
  {
    rotulo: "Título",
    celula: ({ posicao, calculada }) =>
      celula(
        `<strong>${esc(posicao.nome)}</strong>`,
        observacaoDe(posicao),
        erroDe(calculada)
      ),
  },
  {
    rotulo: "Remuneração",
    celula: ({ calculada }) =>
      celula(esc(calculada?.rotulo_taxa || "—"), origemDaTaxa(calculada)),
  },
  COLUNA_VENCIMENTO,
  {
    rotulo: "Na curva",
    num: true,
    mono: true,
    celula: ({ calculada }) =>
      calculada?.valor_na_curva == null
        ? "—"
        : celula(moeda(calculada.valor_na_curva), "se levar ao vencimento"),
  },
  COLUNA_LIQUIDO,
];

// ── Colunas comuns a todas as classes ──────

/** Onde um peso cai na barra, em porcentagem do fundo de escala. */
const naEscala = (valor) => `${((valor / estado.escalaPeso) * 100).toFixed(1)}%`;

/** Peso da posição: o número e, abaixo, a barra na cor da classe do ativo. */
function celulaPeso({ posicao, calculada }) {
  if (!calculada) return "—";
  const limite = Number(estado.dados.limite) || 0;
  const acima = limite > 0 && calculada.peso_pct > limite;
  const traco =
    limite > 0 && limite <= estado.escalaPeso
      ? `<div class="trilho-limite" style="left:${naEscala(limite)}"></div>`
      : "";
  return `<div class="peso">
    <span${acima ? ' class="peso-acima"' : ""}>${pct(calculada.peso_pct, 1, false)}</span>
    <div class="trilho trilho-peso">
      <div class="trilho-preenche" style="width:${naEscala(calculada.peso_pct)};background:var(--${posicao.tipo})"></div>
      ${traco}
    </div>
  </div>`;
}

function celulaAcoes({ posicao }) {
  const nome = esc(nomeDaLinha(posicao));
  return `<button class="btn-icone" data-editar="${posicao.id}" title="Editar"
      aria-label="Editar ${nome}">${icone("editar", 16)}</button>
    <button class="btn-icone perigo" data-excluir="${posicao.id}" title="Excluir"
      aria-label="Excluir ${nome}">${icone("excluir", 16)}</button>`;
}

const COLUNAS_COMUNS = [
  {
    rotulo: "Valor",
    num: true,
    mono: true,
    celula: ({ calculada }) =>
      !calculada
        ? "—"
        : celula(
            moeda(calculada.valor_atual),
            calculada.marcado_a_mercado ? `mercado de ${dataBR(calculada.cotacao_em)}` : ""
          ),
  },
  {
    rotulo: "Resultado",
    num: true,
    mono: true,
    celula: ({ calculada }) =>
      calculada ? textoResultado(calculada.resultado, calculada.resultado_pct) : "—",
  },
  { rotulo: "Peso", num: true, mono: true, celula: celulaPeso },
  { rotulo: "", num: true, classe: "acoes", celula: celulaAcoes },
];

const GRUPOS = [
  { tipo: "fii", rotulo: "Fundos imobiliários", colunas: COLUNAS_VARIAVEL },
  { tipo: "acao", rotulo: "Ações", colunas: COLUNAS_VARIAVEL },
  { tipo: "cdb", rotulo: "CDBs", colunas: COLUNAS_CDB },
  { tipo: "tesouro", rotulo: "Tesouro Direto", colunas: COLUNAS_TESOURO },
];

/** Alinhamento e fonte da célula saem da declaração da coluna, não do HTML. */
function celulaDoAtivo(coluna, item) {
  const classes = [coluna.num && "num", coluna.mono && "mono", coluna.classe].filter(Boolean);
  const atributo = classes.length ? ` class="${classes.join(" ")}"` : "";
  return `<td${atributo}>${coluna.celula(item)}</td>`;
}

// ── Busca e ordenação ──────────────────────

const ORDENS = {
  valor: { rotulo: "Maior valor", chave: (i) => -(i.calculada?.valor_atual ?? 0) },
  resultado: { rotulo: "Melhor resultado", chave: (i) => -(i.calculada?.resultado_pct ?? 0) },
  nome: { rotulo: "Nome (A–Z)", chave: (i) => semAcento(nomeDaLinha(i.posicao)) },
  vencimento: {
    rotulo: "Vencimento mais próximo",
    chave: (i) => i.posicao.data_vencimento || "9999-12-31",
  },
};

/** Tudo o que a busca enxerga numa posição: cadastro, cálculo e ficha da IA. */
const textoBuscavel = ({ posicao, calculada, ficha }) =>
  semAcento(
    [
      ROTULO_TIPO[posicao.tipo],
      posicao.ticker,
      posicao.banco,
      posicao.nome,
      posicao.observacao,
      ficha?.nome,
      ficha?.segmento,
      ficha?.gestora,
      calculada?.rotulo_taxa,
    ]
      .filter(Boolean)
      .join(" ")
  );

function ordenar(itens) {
  const { chave } = ORDENS[estado.ordem] || ORDENS.valor;
  return [...itens].sort((a, b) => {
    const [x, y] = [chave(a), chave(b)];
    return x < y ? -1 : x > y ? 1 : 0;
  });
}

// ── Desenho ────────────────────────────────

function montarItens() {
  const { posicoes = [], snapshot, fundamentos } = estado.dados;
  const calculadas = indexar(snapshot?.posicoes, "id");
  const fichas = indexar(fundamentos?.fichas, "ticker");
  return posicoes.map((posicao) => ({
    posicao,
    calculada: calculadas[posicao.id] || null,
    ficha: fichas[posicao.ticker] || null,
  }));
}

/** Fundo de escala das barras de peso: o maior peso, ou o limite se for maior. */
const escalaDoPeso = (itens) =>
  Math.max(...itens.map((i) => i.calculada?.peso_pct ?? 0), Number(estado.dados.limite) || 0, 1);

function totaisDoGrupo(itens) {
  const soma = (campo) => itens.reduce((total, i) => total + (i.calculada?.[campo] ?? 0), 0);
  const investido = soma("valor_investido");
  const resultado = soma("resultado");
  return {
    calculado: itens.some((i) => i.calculada),
    valor: soma("valor_atual"),
    resultado,
    resultadoPct: investido ? (resultado / investido) * 100 : 0,
    pesoPct: soma("peso_pct"),
  };
}

/** Cabeçalho do grupo: o botão que recolhe, à esquerda; o subtotal, à direita. */
function linhaDoGrupo(grupo, itens) {
  const totais = totaisDoGrupo(itens);
  const aberto = !estado.recolhidos.has(grupo.tipo);
  const plural = itens.length === 1 ? "posição" : "posições";
  return `<tr class="linha-grupo">
    <th colspan="${grupo.colunas.length}" scope="colgroup">
      <button type="button" class="botao-grupo" data-grupo="${grupo.tipo}" aria-expanded="${aberto}">
        <span class="seta-grupo">${icone("seta", 15)}</span>
        <span class="etiqueta etiqueta-${grupo.tipo}">${ROTULO_TIPO[grupo.tipo]}</span>
        <span class="grupo-rotulo">${grupo.rotulo}</span>
        <span class="grupo-contagem">${itens.length} ${plural}</span>
      </button>
    </th>
    <td class="num mono">${totais.calculado ? moeda(totais.valor) : "—"}</td>
    <td class="num mono">${
      totais.calculado ? textoResultado(totais.resultado, totais.resultadoPct) : "—"
    }</td>
    <td class="num mono">${totais.calculado ? pct(totais.pesoPct, 1, false) : "—"}</td>
    <td></td>
  </tr>`;
}

function desenharGrupo({ grupo, itens }) {
  const colunas = [...grupo.colunas, ...COLUNAS_COMUNS];
  const cabecalho = colunas.map((c) => `<th${c.num ? ' class="num"' : ""}>${c.rotulo}</th>`).join("");
  const linhas = itens
    .map((item) => `<tr>${colunas.map((c) => celulaDoAtivo(c, item)).join("")}</tr>`)
    .join("");

  return `<tbody class="grupo-ativos${estado.recolhidos.has(grupo.tipo) ? " recolhido" : ""}">
    ${linhaDoGrupo(grupo, itens)}
    <tr class="linha-colunas">${cabecalho}</tr>
    ${linhas}
  </tbody>`;
}

const mensagemVazia = (total) =>
  total
    ? `Nenhuma posição encontrada para “${esc(estado.termo)}”.`
    : "Nenhuma posição cadastrada. Clique em “+ Nova posição”.";

function desenhar() {
  const itens = montarItens();
  estado.escalaPeso = escalaDoPeso(itens);
  mostrar("#filtros-posicoes", itens.length > 0);

  const termo = semAcento(estado.termo);
  const visiveis = termo ? itens.filter((i) => textoBuscavel(i).includes(termo)) : itens;
  const grupos = GRUPOS.map((grupo) => ({
    grupo,
    itens: ordenar(visiveis.filter((i) => i.posicao.tipo === grupo.tipo)),
  })).filter(({ itens: doGrupo }) => doGrupo.length);

  $("#posicoes").innerHTML = grupos.length
    ? `<div class="tabela-rolagem">
        <table class="tabela tabela-posicoes">${grupos.map(desenharGrupo).join("")}</table>
      </div>`
    : `<div class="vazio">${mensagemVazia(itens.length)}</div>`;

  const todosRecolhidos =
    grupos.length > 0 && grupos.every(({ grupo }) => estado.recolhidos.has(grupo.tipo));
  $("#btn-recolher").textContent = todosRecolhidos ? "Expandir tudo" : "Recolher tudo";
}

/**
 * Desenha a listagem.
 *
 * @param {object} dados `posicoes` (cadastro), `snapshot` (cálculo),
 *   `fundamentos` (fichas da IA) e `limite` de concentração em vigor.
 * @param {{editar: Function, excluir: Function}} acoes
 */
export function renderPosicoes(dados, acoes) {
  estado.dados = dados || { posicoes: [] };
  estado.acoes = acoes;
  desenhar();
}

// ── Controles da tela ──────────────────────

function alternarGrupo(tipo) {
  if (!estado.recolhidos.delete(tipo)) estado.recolhidos.add(tipo);
  desenhar();
}

/** Recolhe todos os grupos na tela; se já estiverem todos recolhidos, expande. */
function alternarTodos() {
  const tipos = GRUPOS.map((g) => g.tipo).filter((tipo) => $(`[data-grupo="${tipo}"]`));
  const todosRecolhidos = tipos.every((tipo) => estado.recolhidos.has(tipo));
  tipos.forEach((tipo) =>
    todosRecolhidos ? estado.recolhidos.delete(tipo) : estado.recolhidos.add(tipo)
  );
  desenhar();
}

function aoClicarNaLista(evento) {
  const botao = evento.target.closest("[data-grupo], [data-editar], [data-excluir]");
  if (!botao) return;
  if (botao.dataset.grupo) alternarGrupo(botao.dataset.grupo);
  else if (botao.dataset.editar) estado.acoes.editar(botao.dataset.editar);
  else estado.acoes.excluir(botao.dataset.excluir);
}

/**
 * Liga busca, ordenação e recolhimento. Os cliques da tabela são ouvidos no
 * contêiner, que sobrevive a cada redesenho — os botões das linhas, não.
 */
export function ligarPosicoes() {
  $("#ordem-posicoes").innerHTML = Object.entries(ORDENS)
    .map(([valor, { rotulo }]) => `<option value="${valor}">${rotulo}</option>`)
    .join("");
  $("#ordem-posicoes").value = estado.ordem;

  $("#busca-posicoes").addEventListener("input", (ev) => {
    estado.termo = ev.target.value.trim();
    desenhar();
  });
  $("#ordem-posicoes").addEventListener("change", (ev) => {
    estado.ordem = ev.target.value;
    desenhar();
  });
  $("#btn-recolher").addEventListener("click", alternarTodos);
  $("#posicoes").addEventListener("click", aoClicarNaLista);
}

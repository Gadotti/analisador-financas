/**
 * Quadro "Alocação e concentração".
 *
 * Uma base e uma régua: todos os recortes são percentuais da carteira inteira
 * (é o que `fundamentals._agrupar` devolve) e todos usam o mesmo limite de
 * concentração configurado pelo usuário, desenhado como traço na barra.
 */

import { $, esc, moeda, moedaCurta, pct } from "./formato.js";
import { icone } from "./icones.js";

const COR_CLASSE = {
  fii: "var(--fii)",
  acao: "var(--acao)",
  cdb: "var(--cdb)",
  tesouro: "var(--tesouro)",
};

const corDe = (tipo) => COR_CLASSE[tipo] || "var(--t3)";

/** Barra com o traço do limite por cima. */
function trilho(pesoPct, cor, limitePct) {
  const largura = Math.min(pesoPct, 100);
  return `<div class="trilho">
    <div class="trilho-preenche" style="width:${largura}%;background:${cor}"></div>
    <div class="trilho-limite" style="left:${Math.min(limitePct, 100)}%"></div>
  </div>`;
}

function faixaClasses(classes) {
  const fatias = Object.entries(classes)
    .map(([chave, c]) => `<div style="width:${c.peso_pct}%;background:${corDe(chave)}"></div>`)
    .join("");

  const legenda = Object.entries(classes)
    .map(
      ([chave, c]) => `<div class="legenda-classe">
        <span class="legenda-ponto" style="background:${corDe(chave)}"></span>
        <span style="flex-grow:1"><strong>${esc(c.rotulo)}</strong>
          <span class="indicador-sub">${c.posicoes} ativo(s)</span></span>
        <span class="num"><span class="mono" style="font-weight:600">${pct(c.peso_pct, 1, false)}</span>
          <span class="mono indicador-sub">${moedaCurta(c.valor_atual)}</span></span>
      </div>`
    )
    .join("");

  return `<div class="faixa-classes">${fatias}</div>
    <div class="legenda-classes">${legenda}</div>`;
}

function linhaGrupo(grupo, limitePct) {
  const acima = grupo.peso_pct > limitePct;
  const selo = acima
    ? '<span class="pilula pilula-limite">acima do limite</span>'
    : "";
  const tickers = grupo.ativos
    .map((t) => `<span class="ticker mono">${esc(t)}</span>`)
    .join("");

  return `<div class="grupo">
    <div class="grupo-cabeca">
      <span class="grupo-nome">${esc(grupo.nome)} ${selo}</span>
      <span class="grupo-peso mono ${acima ? "acima" : ""}">${pct(grupo.peso_pct, 1, false)}</span>
    </div>
    ${trilho(grupo.peso_pct, corDe(grupo.tipo), limitePct)}
    <div class="grupo-pe">
      <div class="tickers">${tickers}</div>
      <span class="grupo-valor mono">${moedaCurta(grupo.valor)}</span>
    </div>
  </div>`;
}

/** Faixa hachurada com a parte da carteira que nenhum recorte alcança. */
function linhaDescoberto(naoCoberto, explicar) {
  if (!naoCoberto?.valor) return "";
  const nota = explicar
    ? `<div class="fgc">Renda fixa não recebe ficha da IA, então fica fora dos recortes.</div>`
    : "";
  return `<div class="grupo grupo-descoberto">
    <div class="grupo-cabeca">
      <span class="grupo-nome">Sem ficha · renda fixa</span>
      <span class="grupo-peso mono">${pct(naoCoberto.peso_pct, 1, false)}</span>
    </div>
    <div class="trilho">
      <div class="trilho-preenche hachura" style="width:${naoCoberto.peso_pct}%"></div>
    </div>
    ${nota}
  </div>`;
}

/**
 * Rodapé da linha do emissor: o consumo do teto do FGC num banco; a garantia
 * soberana no Tesouro Direto, que o FGC não cobre — nem precisa cobrir.
 */
function coberturaDoEmissor(emissor) {
  if (!emissor.fgc_limite) {
    return `<span class="fgc">${moeda(emissor.valor)} · garantia do Tesouro Nacional</span>
      <span class="grupo-valor mono">sem FGC</span>`;
  }
  return `<span class="fgc ${emissor.acima_do_fgc ? "estourado" : ""}">
      ${moeda(emissor.valor)} de ${moedaCurta(emissor.fgc_limite)} do FGC</span>
    <span class="grupo-valor mono">${pct(emissor.fgc_uso_pct, 0, false)}</span>`;
}

function blocoEmissores(emissores, limitePct) {
  if (!emissores?.length) return "";

  const linhas = emissores
    .map(
      (e) => `<div class="grupo">
        <div class="grupo-cabeca">
          <span class="grupo-nome">${esc(e.nome)}</span>
          <span class="grupo-peso mono ${e.peso_pct > limitePct ? "acima" : ""}">${pct(e.peso_pct, 1, false)}</span>
        </div>
        ${trilho(e.peso_pct, corDe(e.fgc_limite ? "cdb" : "tesouro"), limitePct)}
        <div class="grupo-pe">${coberturaDoEmissor(e)}</div>
      </div>`
    )
    .join("");

  return `<div class="emissores">
    <div class="emissores-titulo">${icone("escudo", 14)}<span class="microrotulo" style="color:inherit">Emissores de renda fixa</span></div>
    ${linhas}
  </div>`;
}

function colunaRecorte(titulo, grupos, limitePct, rodape = "") {
  const corpo = grupos.length
    ? grupos.map((g) => linhaGrupo(g, limitePct)).join("")
    : '<div class="fgc">Depende da análise por IA.</div>';

  return `<div class="recorte">
    <div class="recorte-topo">
      <span class="microrotulo">${titulo}</span>
      <span class="mono grupo-valor">${grupos.length} grupo(s)</span>
    </div>
    ${corpo}${rodape}
  </div>`;
}

const legendaRegua = (limitePct) => `<div class="legenda-regua">
  <div><span class="amostra-limite"></span>
    <span>Limite de concentração configurado — ${pct(limitePct, 0, false)}</span></div>
  <div><span class="amostra-faixa hachura"></span>
    <span>Parte da carteira que o recorte não cobre</span></div>
  <div><span class="amostra-faixa" style="background:linear-gradient(90deg,var(--fii) 0 50%,var(--acao) 50% 100%)"></span>
    <span>A barra herda a cor da classe do ativo</span></div>
</div>`;

/**
 * Desenha o quadro inteiro.
 *
 * @param {object} snapshot Cálculo determinístico da carteira.
 * @param {object|null} fundamentos Recortes por ficha; ausente sem análise de IA.
 * @param {number} limitePct Limite de concentração configurado.
 */
export function renderAlocacao(snapshot, fundamentos, limitePct) {
  const classes = Object.entries(snapshot.classes);
  if (!classes.length) {
    $("#alocacao").innerHTML = '<div class="vazio">Nenhuma posição cadastrada.</div>';
    $("#alocacao-base").innerHTML = "";
    return;
  }

  const naoCoberto = fundamentos?.nao_coberto;
  const emissores = snapshot.emissores_renda_fixa || [];

  $("#alocacao-base").innerHTML =
    `<span class="pilula mono">Base: carteira · ${moeda(snapshot.totais.valor_atual)}</span>
     <span class="pilula pilula-limite mono">Limite ${pct(limitePct, 0, false)}</span>`;

  $("#alocacao").innerHTML =
    faixaClasses(snapshot.classes) +
    `<div class="recortes">
      ${colunaRecorte("Por classificação", fundamentos?.por_classificacao || [], limitePct, linhaDescoberto(naoCoberto, true))}
      ${colunaRecorte("Por segmento", fundamentos?.por_segmento || [], limitePct, linhaDescoberto(naoCoberto, false))}
      ${colunaRecorte("Por gestora / emissor", fundamentos?.por_gestora || [], limitePct, blocoEmissores(emissores, limitePct))}
    </div>` +
    legendaRegua(limitePct);
}

/** Tela "Visão geral": contexto macro, posição consolidada, alocação e riscos. */

import { trilho } from "./alocacao.js";
import { cartaoAlertaRecolhido, listaAlertas } from "./alertas.js";
import { $, $$, classeSinal, corClasse, dataHoraBR, esc, moeda, moedaCurta, mostrar, num, pct } from "./formato.js";
import { icone } from "./icones.js";

const ROTULO_SAUDE = { otima: "Ótima", boa: "Boa", atencao: "Atenção", alerta: "Alerta" };
const COR_SINAL = { pos: "var(--verde)", neg: "var(--vermelho)", zero: "var(--t3)" };

// ── Hero: valor de mercado, resultado e a quebra por regime ──────────

// A mesma fronteira de `portfolio.TIPOS_VARIAVEL` / `TIPOS_RENDA_FIXA` —
// só para agrupar o que `snapshot.classes` já calculou, sem refazer conta.
const GRUPOS_RESULTADO = [
  { chave: "variavel", rotulo: "Renda variável", tipos: ["fii", "acao"] },
  { chave: "fixa", rotulo: "Renda fixa", tipos: ["cdb", "tesouro"] },
];

/** Soma o que `analysis.consolidar` já calculou por classe, agora por regime. */
function agruparResultadoPorRegime(classes) {
  return GRUPOS_RESULTADO.map(({ chave, rotulo, tipos }) => {
    const itens = tipos.filter((tipo) => classes[tipo]).map((tipo) => ({ tipo, ...classes[tipo] }));
    const investido = itens.reduce((soma, c) => soma + c.valor_investido, 0);
    const atual = itens.reduce((soma, c) => soma + c.valor_atual, 0);
    const resultado = atual - investido;
    return {
      chave,
      rotulo,
      itens,
      investido,
      atual,
      resultado,
      resultado_pct: investido ? (resultado / investido) * 100 : 0,
    };
  }).filter((grupo) => grupo.itens.length > 0);
}

const chipClasse = (item) => `
  <div class="resultado-chip">
    <span class="legenda-ponto" style="background:${corClasse(item.tipo)}"></span>
    <span class="resultado-chip-nome">${esc(item.rotulo)}</span>
    <span class="mono ${classeSinal(item.resultado)}">${moeda(item.resultado)}</span>
  </div>`;

function barraRegime(grupo) {
  const sinal = classeSinal(grupo.resultado);
  return `<div class="regime">
    <div class="regime-cabeca">
      <span class="regime-nome">${esc(grupo.rotulo)}</span>
      <span class="mono ${sinal}">${moeda(grupo.resultado)} <span class="indicador-sub">(${pct(grupo.resultado_pct)})</span></span>
    </div>
    ${trilho(grupo.resultado_pct, COR_SINAL[sinal])}
    <div class="resultado-chips">${grupo.itens.map(chipClasse).join("")}</div>
  </div>`;
}

/** Quebra o "Resultado acumulado" no que veio de renda variável e de renda fixa. */
function blocoRegimes(classes) {
  const grupos = agruparResultadoPorRegime(classes);
  if (grupos.length < 2) return "";
  return `<div class="resultado-regimes">${grupos.map(barraRegime).join("")}</div>`;
}

function hero(snapshot) {
  const t = snapshot.totais;
  const saude = snapshot.saude_carteira;
  const sinal = classeSinal(t.resultado);

  const chipDia = t.resultado_dia
    ? `<div class="hero-chip">
        <span class="microrotulo">Variação do dia</span>
        <span class="mono ${classeSinal(t.resultado_dia)}">${moeda(t.resultado_dia)}</span>
      </div>`
    : "";

  return `
    <div class="hero-topo">
      <div>
        <span class="microrotulo">Valor de mercado</span>
        <div class="hero-valor mono">${moeda(t.valor_atual)}</div>
        <div class="indicador-sub">custo ${moedaCurta(t.valor_investido)} · ${t.posicoes} posições</div>
      </div>
      <span class="selo selo-${saude}">${ROTULO_SAUDE[saude] || saude}</span>
    </div>
    <div class="hero-resultado">
      <div>
        <span class="microrotulo">Resultado acumulado</span>
        <div class="hero-valor2 mono ${sinal}">${moeda(t.resultado)}</div>
        <div class="indicador-sub"><span class="${sinal}">${pct(t.resultado_pct)}</span> desde a compra</div>
      </div>
      ${chipDia}
    </div>
    ${blocoRegimes(snapshot.classes)}`;
}

// ── Indicadores de ficha (P/VP, DY, YoC, renda estimada) ──────────────

/** Métricas de valuation e renda calculadas por `fundamentals` — só existem quando a IA devolveu fichas. */
function metricasFicha(metricas) {
  if (!metricas) return [];
  const linhas = [];

  if (metricas.p_vp_medio) {
    const leitura = metricas.p_vp_medio < 1 ? "desconto patrimonial" : "ágio patrimonial";
    linhas.push({
      chave: "pvp",
      rotulo: "P/VP médio",
      valor: num(metricas.p_vp_medio, 2),
      sub: `${leitura} · ${metricas.p_vp_cobertura} com dado`,
    });
  }
  if (metricas.dy_medio_pct) {
    linhas.push({
      chave: "dy",
      rotulo: "DY médio",
      valor: pct(metricas.dy_medio_pct, 2, false),
      sub: `cobertura ${metricas.dy_cobertura}`,
    });
    // O YoC mede a mesma renda contra o que foi pago; sem o rótulo da base os
    // dois números pareceriam divergir sobre a mesma coisa.
    if (metricas.yoc_medio_pct) {
      linhas.push({
        chave: "yoc",
        rotulo: "YoC médio",
        valor: pct(metricas.yoc_medio_pct, 2, false),
        sub: `sobre o preço médio · cobertura ${metricas.yoc_cobertura}`,
      });
    }
    linhas.push({
      chave: "renda",
      rotulo: "Renda estimada",
      valor: moeda(metricas.renda_mensal_estimada),
      sub: `por mês · ${moeda(metricas.renda_anual_estimada)} ao ano`,
    });
  }
  return linhas;
}

const ICONE_METRICA = { pvp: "balanca", dy: "moeda", yoc: "moeda", renda: "moeda" };

const tileFicha = (m) => `
  <div class="ficha-tile">
    <span class="ficha-tile-icone">${icone(ICONE_METRICA[m.chave] || "analise", 17)}</span>
    <div>
      <span class="microrotulo">${esc(m.rotulo)}</span>
      <div class="ficha-tile-valor mono">${m.valor}</div>
      <div class="indicador-sub">${esc(m.sub)}</div>
    </div>
  </div>`;

function renderFundamentos(metricas) {
  const linhas = metricasFicha(metricas);
  mostrar("#fundamentos-cartao", linhas.length > 0);
  $("#fundamentos").innerHTML = linhas.map(tileFicha).join("");
}

/**
 * @param {string|null} herdadaDe Quando o texto da IA vem de uma análise
 *   anterior — só as cotações são desta execução.
 */
export function renderResumo(snapshot, ia, fundamentos, herdadaDe = null) {
  const origem = herdadaDe ? ` · leitura por IA de ${dataHoraBR(herdadaDe)}` : "";
  $("#resumo-quando").textContent = "atualizado em " + dataHoraBR(snapshot.gerado_em) + origem;
  $("#hero").innerHTML = hero(snapshot);

  renderFundamentos(fundamentos?.metricas);
  renderContexto(ia);
}

/** Recolhido por padrão: o texto corrido só aparece a quem for atrás dele. */
const blocoContexto = (titulo, texto) => `
  <details class="bloco-contexto">
    <summary>
      <span class="bloco-titulo">${titulo}</span>
      <span class="bloco-seta">${icone("seta", 16)}</span>
    </summary>
    <p>${esc(texto)}</p>
  </details>`;

/** As leituras de cenário e de carteira da IA, ao pé da posição consolidada. */
function renderContexto(ia) {
  const blocos = [];
  if (ia?.contexto_mercado) blocos.push(blocoContexto("Contexto de mercado", ia.contexto_mercado));
  if (ia?.resumo) blocos.push(blocoContexto("Contexto da carteira", ia.resumo));

  mostrar("#contexto-mercado", blocos.length > 0);
  $("#contexto-mercado").innerHTML = blocos.join("");
}

function itensMacro(macro) {
  const itens = [
    ["CDI", `${num(macro.cdi_anual_pct.valor)}% a.a.`],
    ["Selic meta", `${num(macro.selic_meta_pct.valor)}% a.a.`],
    ["IPCA 12m", `${num(macro.ipca_12m_pct.valor)}%`],
  ];
  const ibov = macro.indices?.ibovespa;
  if (ibov) {
    itens.push([
      "Ibovespa",
      `${Math.round(ibov.valor).toLocaleString("pt-BR")} pts (${pct(ibov.variacao_dia_pct)})`,
    ]);
  }
  return itens;
}

/**
 * O mesmo quadro aparece na visão geral e na tela de equivalência, onde o CDI
 * é a base da conta — por isso os alvos vêm por atributo, e não por id.
 */
export function renderMacro(snapshot) {
  const macro = snapshot.macro;
  const consultadoEm = macro.consultado_em || snapshot.gerado_em;
  const html = itensMacro(macro)
    .map(
      ([k, v]) =>
        `<div class="macro-item"><span class="microrotulo">${k}</span><span class="macro-v mono">${v}</span></div>`
    )
    .join("");

  $$("[data-macro-quando]").forEach((el) => {
    el.textContent = consultadoEm ? "atualizado em " + dataHoraBR(consultadoEm) : "";
  });
  $$("[data-macro]").forEach((el) => (el.innerHTML = html));
}

export function renderRiscos(snapshot, ia) {
  const partes = [];

  if (snapshot.alertas.length) {
    partes.push('<div class="subtitulo">Detectados pelo cálculo da carteira</div>');
    partes.push(
      '<div class="alertas">' +
        snapshot.alertas
          .map((a) => cartaoAlertaRecolhido(a.severidade, esc(a.titulo), esc(a.descricao)))
          .join("") +
        "</div>"
    );
  }

  if (ia?.riscos?.length) {
    partes.push('<div class="subtitulo">Levantados na análise, por relevância</div>');
    partes.push(
      '<div class="alertas">' +
        ia.riscos
          .map((r, i) =>
            cartaoAlertaRecolhido(
              r.severidade,
              `<span class="ordem">${i + 1}</span> ${esc(r.titulo)}`,
              esc(r.descricao),
              r.ativos?.length ? esc(r.ativos.join(", ")) : ""
            )
          )
          .join("") +
        "</div>"
    );
  }

  const total = snapshot.alertas.length + (ia?.riscos?.length || 0);
  $("#riscos-contagem").textContent = total ? `${total} no total` : "";
  $("#riscos").innerHTML =
    partes.join("") ||
    '<div class="vazio">Nenhum risco sinalizado — vencimentos, concentração e FGC dentro dos limites.</div>';
}

/** Cartão irmão do de riscos: o que a IA levantou de fato novo e de observação. */
export function renderFatos(ia) {
  const corpo =
    listaAlertas("Fatos recentes", ia?.fatos, true) +
    listaAlertas("Pontos de observação", ia?.oportunidades);

  const total = (ia?.fatos?.length || 0) + (ia?.oportunidades?.length || 0);
  $("#fatos-contagem").textContent = total ? `${total} no total` : "";
  $("#fatos").innerHTML =
    corpo ||
    '<div class="vazio">Nada levantado na última análise — fatos e pontos de observação vêm da leitura por IA.</div>';
}

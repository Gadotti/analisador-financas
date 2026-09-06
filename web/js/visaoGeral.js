/** Tela "Visão geral": contexto macro, posição consolidada e riscos. */

import { cartaoAlertaRecolhido, listaAlertas } from "./alertas.js";
import { $, $$, classeSinal, corClasse, dataHoraBR, esc, moeda, moedaCurta, mostrar, num, pct } from "./formato.js";
import { icone } from "./icones.js";

const ROTULO_SAUDE = { otima: "Ótima", boa: "Boa", atencao: "Atenção", alerta: "Alerta" };

const indicador = (rotulo, valor, sub, classe = "") => `
  <div class="indicador ${classe}">
    <span class="microrotulo">${rotulo}</span>
    <span class="indicador-valor">${valor}</span>
    <span class="indicador-sub">${sub}</span>
  </div>`;

/** Indicadores de valuation e renda — só existem quando a IA devolveu fichas. */
function indicadoresDeFicha(metricas) {
  if (!metricas) return [];
  const linhas = [];

  if (metricas.p_vp_medio) {
    const leitura = metricas.p_vp_medio < 1 ? "desconto patrimonial" : "ágio patrimonial";
    linhas.push(
      indicador("P/VP médio", num(metricas.p_vp_medio, 2), `${leitura} · ${metricas.p_vp_cobertura} com dado`)
    );
  }
  if (metricas.dy_medio_pct) {
    linhas.push(
      indicador("DY médio", pct(metricas.dy_medio_pct, 2, false), `cobertura ${metricas.dy_cobertura}`)
    );
    // O YoC mede a mesma renda contra o que foi pago; sem o rótulo da base os
    // dois números pareceriam divergir sobre a mesma coisa.
    if (metricas.yoc_medio_pct) {
      linhas.push(
        indicador(
          "YoC médio",
          pct(metricas.yoc_medio_pct, 2, false),
          `sobre o preço médio · cobertura ${metricas.yoc_cobertura}`
        )
      );
    }
    linhas.push(
      indicador(
        "Renda estimada",
        moeda(metricas.renda_mensal_estimada),
        `por mês · ${moeda(metricas.renda_anual_estimada)} ao ano`
      )
    );
  }
  return linhas;
}

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

/** Faixa proporcional a quanto cada regime pesou no resultado, em módulo —
 * evita larguras negativas ou acima de 100% quando um regime perde e o outro ganha. */
function faixaContribuicao(grupos) {
  const totalAbs = grupos.reduce((soma, g) => soma + Math.abs(g.resultado), 0);
  if (!totalAbs) return "";
  const cor = (g) => ({ pos: "var(--verde)", neg: "var(--vermelho)", zero: "var(--t3)" }[classeSinal(g.resultado)]);
  const fatias = grupos
    .map((g) => `<div style="width:${(Math.abs(g.resultado) / totalAbs) * 100}%;background:${cor(g)}"></div>`)
    .join("");
  return `<div class="faixa-classes">${fatias}</div>`;
}

const chipClasse = (item) => `
  <div class="resultado-chip">
    <span class="legenda-ponto" style="background:${corClasse(item.tipo)}"></span>
    <span class="resultado-chip-nome">${esc(item.rotulo)}</span>
    <span class="mono ${classeSinal(item.resultado)}">${moeda(item.resultado)}</span>
  </div>`;

const painelResultado = (g) => `
  <div class="resultado-coluna">
    <div class="resultado-coluna-cabeca">
      <span class="resultado-coluna-nome">${esc(g.rotulo)}</span>
      <span class="resultado-coluna-valor mono ${classeSinal(g.resultado)}">${moeda(g.resultado)}</span>
    </div>
    <div class="indicador-sub">
      <span class="${classeSinal(g.resultado)}">${pct(g.resultado_pct)}</span>
      · valor atual ${moedaCurta(g.atual)} · custo ${moedaCurta(g.investido)}
    </div>
    <div class="resultado-chips">${g.itens.map(chipClasse).join("")}</div>
  </div>`;

/** Quebra o "Resultado acumulado" no que veio de renda variável e de renda fixa. */
function renderResultadoDetalhado(snapshot) {
  const grupos = agruparResultadoPorRegime(snapshot.classes);
  const alvo = $("#resultado-detalhado");
  if (grupos.length < 2) {
    alvo.innerHTML = "";
    return;
  }
  alvo.innerHTML = `
    <div class="resultado-detalhado-topo"><span class="microrotulo">Resultado por tipo de ativo</span></div>
    ${faixaContribuicao(grupos)}
    <div class="resultado-colunas">${grupos.map(painelResultado).join("")}</div>`;
}

/**
 * @param {string|null} herdadaDe Quando o texto da IA vem de uma análise
 *   anterior — só as cotações são desta execução.
 */
export function renderResumo(snapshot, ia, fundamentos, herdadaDe = null) {
  const t = snapshot.totais;
  const saude = snapshot.saude_carteira;

  const origem = herdadaDe ? ` · leitura por IA de ${dataHoraBR(herdadaDe)}` : "";
  $("#resumo-quando").textContent = "atualizado em " + dataHoraBR(snapshot.gerado_em) + origem;

  const sinal = classeSinal(t.resultado);
  const linhas = [
    indicador("Valor de mercado", moeda(t.valor_atual), `custo ${moeda(t.valor_investido)}`, "indicador-hero"),
    indicador(
      "Resultado acumulado",
      `<span class="${sinal}">${moeda(t.resultado)}</span>`,
      `<span class="${sinal}">${pct(t.resultado_pct)}</span>`
    ),
    indicador(
      "Saúde",
      `<span class="selo selo-${saude}">${ROTULO_SAUDE[saude] || saude}</span>`,
      `${snapshot.alertas.length} alerta(s) · ${t.posicoes} posições`
    ),
  ];

  if (t.resultado_dia) {
    const sinalDia = classeSinal(t.resultado_dia);
    linhas.push(
      indicador("Variação do dia", `<span class="${sinalDia}">${moeda(t.resultado_dia)}</span>`, "renda variável")
    );
  }

  $("#indicadores").innerHTML = linhas.concat(indicadoresDeFicha(fundamentos?.metricas)).join("");
  renderResultadoDetalhado(snapshot);
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

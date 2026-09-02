/** Tela "Visão geral": contexto macro, posição consolidada e riscos. */

import { cartaoAlerta, listaAlertas } from "./alertas.js";
import { $, classeSinal, dataHoraBR, esc, moeda, mostrar, num, pct } from "./formato.js";

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
      indicador("DY médio", pct(metricas.dy_medio_pct, 2, false), `cobertura ${metricas.dy_cobertura}`),
      indicador(
        "Renda estimada",
        moeda(metricas.renda_mensal_estimada),
        `por mês · ${moeda(metricas.renda_anual_estimada)} ao ano`
      )
    );
  }
  return linhas;
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
  $("#sumario").innerHTML = ia?.resumo ? `<p class="sumario-texto">${esc(ia.resumo)}</p>` : "";
  mostrar("#sumario", !!ia?.resumo);

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
  renderContextoMercado(ia);
}

/** A leitura de cenário da IA, ao pé da posição consolidada. */
function renderContextoMercado(ia) {
  mostrar("#contexto-mercado", !!ia?.contexto_mercado);
  $("#contexto-mercado").innerHTML = ia?.contexto_mercado
    ? `<div class="bloco-contexto">
         <div class="bloco-titulo">Contexto de mercado</div>
         <p>${esc(ia.contexto_mercado)}</p>
       </div>`
    : "";
}

export function renderMacro(snapshot) {
  const macro = snapshot.macro;
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
  $("#macro").innerHTML = itens
    .map(
      ([k, v]) =>
        `<div class="macro-item"><span class="microrotulo">${k}</span><span class="macro-v mono">${v}</span></div>`
    )
    .join("");
}

export function renderRiscos(snapshot, ia) {
  const partes = [];

  if (snapshot.alertas.length) {
    partes.push('<div class="subtitulo">Detectados pelo cálculo da carteira</div>');
    partes.push(
      '<div class="alertas">' +
        snapshot.alertas
          .map((a) => cartaoAlerta(a.severidade, esc(a.titulo), esc(a.descricao)))
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
            cartaoAlerta(
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

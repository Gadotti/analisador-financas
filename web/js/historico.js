/**
 * Tela "Histórico": evolução do patrimônio e execuções registradas.
 *
 * O gráfico é SVG desenhado à mão — sem biblioteca, para manter a interface
 * sem build. Uma série de dados (valor de mercado) contra uma linha de
 * referência (custo acumulado), na mesma escala e num eixo só.
 */

import {
  $, classeSinal, dataBR, dataHoraBR, diaMes, esc, moeda, moedaCurta, pct,
} from "./formato.js";

const AREA = { largura: 900, altura: 300, esq: 68, dir: 16, topo: 14, base: 42 };
const COR_MERCADO = "var(--azul)";
const COR_CUSTO = "var(--t3)";

/** Rótulo e cor (reaproveitando os tons de `.selo-*`) por status da IA na execução. */
const STATUS_IA = {
  sucesso: { rotulo: "OK", classe: "otima" },
  sem_ia: { rotulo: "Sem IA", classe: "boa" },
  erro_recuperado: { rotulo: "Erro · leitura mantida", classe: "atencao" },
  erro: { rotulo: "Erro", classe: "alerta" },
};

const FALHOU = new Set(["erro", "erro_recuperado"]);

const x0 = AREA.esq;
const x1 = AREA.largura - AREA.dir;
const y0 = AREA.topo;
const y1 = AREA.altura - AREA.base;

/** Escala vertical com folga de 6%, para a linha não encostar na borda. */
function escalaY(serie) {
  const valores = serie.flatMap((p) => [p.valor_atual, p.valor_investido]);
  const minimo = Math.min(...valores);
  const maximo = Math.max(...valores);
  const folga = (maximo - minimo) * 0.06 || Math.abs(maximo) * 0.06 || 1;
  const baixo = minimo - folga;
  const alto = maximo + folga;
  return (valor) => y1 - ((valor - baixo) / (alto - baixo)) * (y1 - y0);
}

const escalaX = (total) => (i) =>
  total < 2 ? (x0 + x1) / 2 : x0 + (i * (x1 - x0)) / (total - 1);

const caminho = (serie, campo, px, py) =>
  serie.map((p, i) => `${i ? "L" : "M"}${px(i).toFixed(1)} ${py(p[campo]).toFixed(1)}`).join(" ");

function grade(serie, py) {
  const valores = serie.flatMap((p) => [p.valor_atual, p.valor_investido]);
  const minimo = Math.min(...valores);
  const maximo = Math.max(...valores);

  return [0, 1, 2, 3]
    .map((i) => {
      const valor = minimo + ((maximo - minimo) * i) / 3;
      const y = py(valor).toFixed(1);
      return `<line x1="${x0}" y1="${y}" x2="${x1}" y2="${y}" stroke="var(--borda)" stroke-width="1"></line>
        <text x="${x0 - 10}" y="${y}" text-anchor="end" dominant-baseline="middle"
          fill="var(--t3)" font-size="11">${moedaCurta(valor)}</text>`;
    })
    .join("");
}

/** Datas no eixo: no máximo seis, para não empilhar rótulos. */
function eixoDatas(serie, px) {
  const passo = Math.max(1, Math.ceil(serie.length / 6));
  return serie
    .map((p, i) =>
      i % passo === 0 || i === serie.length - 1
        ? `<text x="${px(i).toFixed(1)}" y="${y1 + 22}" text-anchor="middle"
             fill="var(--t3)" font-size="11">${diaMes(p.data)}</text>`
        : ""
    )
    .join("");
}

function svgGrafico(serie) {
  const px = escalaX(serie.length);
  const py = escalaY(serie);

  return `<svg class="grafico" viewBox="0 0 ${AREA.largura} ${AREA.altura}" role="img"
      aria-label="Valor de mercado contra custo acumulado ao longo do tempo">
    ${grade(serie, py)}
    ${eixoDatas(serie, px)}
    <path d="${caminho(serie, "valor_investido", px, py)}" fill="none"
      stroke="${COR_CUSTO}" stroke-width="2" stroke-dasharray="5 4"
      stroke-linejoin="round" stroke-linecap="round"></path>
    <path d="${caminho(serie, "valor_atual", px, py)}" fill="none"
      stroke="${COR_MERCADO}" stroke-width="2"
      stroke-linejoin="round" stroke-linecap="round"></path>
    <line id="cruzeta" x1="0" y1="${y0}" x2="0" y2="${y1}"
      stroke="var(--borda-forte)" stroke-width="1" opacity="0"></line>
    <circle id="marca-mercado" r="4.5" fill="${COR_MERCADO}"
      stroke="var(--card)" stroke-width="2" opacity="0"></circle>
    <circle id="marca-custo" r="4.5" fill="${COR_CUSTO}"
      stroke="var(--card)" stroke-width="2" opacity="0"></circle>
    <rect id="captura" x="${x0}" y="${y0}" width="${x1 - x0}" height="${y1 - y0}"
      fill="transparent"></rect>
  </svg>`;
}

const legenda = `<div class="legenda-grafico">
  <div><span class="amostra-linha" style="background:${COR_MERCADO}"></span>
    <span>Valor de mercado</span></div>
  <div><span class="amostra-linha" style="background:repeating-linear-gradient(90deg,${COR_CUSTO} 0 5px,transparent 5px 9px)"></span>
    <span>Custo acumulado</span></div>
</div>`;

const conteudoDica = (ponto) => `
  <div class="mono" style="font-weight:600">${dataBR(ponto.data)}</div>
  <div>Mercado <span class="mono">${moeda(ponto.valor_atual)}</span></div>
  <div>Custo <span class="mono">${moeda(ponto.valor_investido)}</span></div>
  <div class="${classeSinal(ponto.resultado)}">Resultado
    <span class="mono">${moeda(ponto.resultado)} (${pct(ponto.resultado_pct)})</span></div>`;

/** Cruzeta e balão que seguem o ponto mais próximo do cursor. */
function ligarLeituraDoGrafico(serie) {
  const svg = $("#grafico-historico svg");
  const dica = $("#dica-grafico");
  const px = escalaX(serie.length);
  const py = escalaY(serie);
  const marcas = [$("#cruzeta"), $("#marca-mercado"), $("#marca-custo")];

  const esconder = () => {
    marcas.forEach((m) => m.setAttribute("opacity", "0"));
    dica.classList.add("hidden");
  };

  svg.addEventListener("mousemove", (ev) => {
    const caixa = svg.getBoundingClientRect();
    const relativo = ((ev.clientX - caixa.left) / caixa.width) * AREA.largura;
    const proporcao = (relativo - x0) / (x1 - x0);
    const i = Math.max(0, Math.min(serie.length - 1, Math.round(proporcao * (serie.length - 1))));
    const ponto = serie[i];

    $("#cruzeta").setAttribute("x1", px(i));
    $("#cruzeta").setAttribute("x2", px(i));
    $("#marca-mercado").setAttribute("cx", px(i));
    $("#marca-mercado").setAttribute("cy", py(ponto.valor_atual));
    $("#marca-custo").setAttribute("cx", px(i));
    $("#marca-custo").setAttribute("cy", py(ponto.valor_investido));
    marcas.forEach((m) => m.setAttribute("opacity", "1"));

    dica.innerHTML = conteudoDica(ponto);
    dica.classList.remove("hidden");
    const centro = (px(i) / AREA.largura) * caixa.width;
    dica.style.left = `${Math.min(Math.max(centro, 90), caixa.width - 90)}px`;
  });

  svg.addEventListener("mouseleave", esconder);
}

function renderGrafico(serie) {
  if (serie.length < 2) {
    $("#grafico-historico").innerHTML =
      '<div class="vazio">Duas execuções são o mínimo para desenhar a evolução. Rode a análise em dias diferentes.</div>';
    return;
  }
  $("#grafico-historico").innerHTML =
    `<div class="area-grafico">${svgGrafico(serie)}<div class="dica hidden" id="dica-grafico"></div></div>` +
    legenda;
  ligarLeituraDoGrafico(serie);
}

/** Segundos como o usuário lê: "12,4s" abaixo de um minuto, "4min 38s" acima. */
function duracaoBR(segundos) {
  if (segundos == null) return "—";
  if (segundos < 60) return `${segundos.toFixed(1).replace(".", ",")}s`;
  const minutos = Math.floor(segundos / 60);
  return `${minutos}min ${Math.round(segundos - minutos * 60)}s`;
}

/** O selo do status e, abaixo dele, o motivo — que é o que se procura numa falha. */
function celulaStatus(execucao) {
  const status = STATUS_IA[execucao.status_ia] || {
    rotulo: execucao.status_ia || "—",
    classe: "boa",
  };
  const selo = `<span class="selo selo-${status.classe}">${status.rotulo}</span>`;
  if (execucao.ia_erro) {
    // Erro inteiro no title: a linha da tabela mostra o começo e não estica.
    return `${selo}<div class="apoio-erro" title="${esc(execucao.ia_erro)}">${esc(execucao.ia_erro)}</div>`;
  }
  if (execucao.ia_reaproveitada_de) {
    return `${selo}<div class="apoio">leitura de ${dataHoraBR(execucao.ia_reaproveitada_de)}</div>`;
  }
  return selo;
}

function celulaModelo(execucao) {
  if (!execucao.modelo) return "—";
  const detalhes = [execucao.provedor, execucao.effort && `esforço ${execucao.effort}`]
    .filter(Boolean)
    .join(" · ");
  return (
    `<div class="mono">${esc(execucao.modelo)}</div>` +
    (detalhes ? `<div class="apoio">${esc(detalhes)}</div>` : "")
  );
}

const linhaExecucao = (e) => `<tr>
  <td class="mono">${dataHoraBR(e.gerado_em)}</td>
  <td class="num mono">${moeda(e.valor_atual)}</td>
  <td class="num mono ${classeSinal(e.resultado_pct)}">${pct(e.resultado_pct)}</td>
  <td>${celulaStatus(e)}</td>
  <td>${celulaModelo(e)}</td>
  <td class="num mono">${e.buscas_web ?? "—"}</td>
  <td class="num mono">${duracaoBR(e.duracao_s)}</td>
</tr>`;

function renderExecucoes(execucoes) {
  if (!execucoes.length) {
    $("#execucoes-meta").textContent = "";
    $("#tabela-historico").innerHTML =
      '<div class="vazio">Nenhuma execução registrada ainda. O log começa na próxima análise.</div>';
    return;
  }

  const falhas = execucoes.filter((e) => FALHOU.has(e.status_ia)).length;
  $("#execucoes-meta").textContent =
    `${execucoes.length} execução(ões)` + (falhas ? ` · ${falhas} com falha` : "");

  const linhas = [...execucoes].reverse().map(linhaExecucao).join("");
  $("#tabela-historico").innerHTML = `
    <div class="tabela-rolagem">
      <table class="tabela">
        <thead><tr>
          <th>Data e hora</th><th class="num">Valor de mercado</th><th class="num">Resultado</th>
          <th>IA</th><th>Modelo</th><th class="num">Buscas</th><th class="num">Duração</th>
        </tr></thead>
        <tbody>${linhas}</tbody>
      </table>
    </div>`;
}

/**
 * Desenha as duas seções de /api/historico: o gráfico vem da série diária (um
 * ponto por dia) e a tabela, do log de execuções (uma linha por rodada).
 */
export function renderHistorico(serie, execucoes = []) {
  $("#historico-periodo").textContent = serie.length
    ? `${serie.length} dia(s) · de ${dataBR(serie[0].data)} a ${dataBR(serie[serie.length - 1].data)}`
    : "";
  renderGrafico(serie);
  renderExecucoes(execucoes);
}

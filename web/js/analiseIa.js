/** Tela "Análise": fichas por ativo e leitura da carteira pela IA. */

import { cartaoAlerta } from "./alertas.js";
import { $, classeSinal, dataHoraBR, esc, mostrar, num, pct } from "./formato.js";

const BLOCOS_LEITURA = [
  ["Diversificação", "diversificacao"],
  ["Concentração setorial", "concentracao_setorial"],
  ["Concentração de gestor / emissor", "concentracao_gestor"],
  ["Valuation", "valuation"],
  ["Geração de renda", "renda"],
];

function atributos(ficha) {
  return [
    ["Classificação", ficha.classificacao_rotulo],
    ["Segmento", ficha.segmento],
    ["Gestão", ficha.gestora],
    ["Patrimônio", ficha.patrimonio],
    ["P/VP", ficha.p_vp ? num(ficha.p_vp, 2) : null],
    ["DY 12m", ficha.dy_12m_pct ? pct(ficha.dy_12m_pct, 1, false) : null],
    ["Vacância", ficha.vacancia_pct ? pct(ficha.vacancia_pct, 1, false) : null],
    ["Peso", pct(ficha.peso_pct, 1, false)],
  ]
    .filter(([, valor]) => valor)
    .map(
      ([chave, valor]) => `<div class="atributo">
        <span class="microrotulo">${chave}</span>
        <span class="atributo-v mono">${esc(valor)}</span>
      </div>`
    )
    .join("");
}

export function renderFichas(fundamentos) {
  const fichas = fundamentos?.fichas || [];
  mostrar("#cartao-fichas", fichas.length > 0);
  if (!fichas.length) return;

  $("#fichas").innerHTML = fichas
    .map(
      (f) => `<article class="ficha">
        <header class="ficha-topo">
          <div>
            <span class="ficha-ticker mono">${esc(f.ticker)}</span>
            <span class="ficha-nome">${esc(f.nome)}</span>
          </div>
          <span class="mono ${classeSinal(f.resultado_pct)}">${pct(f.resultado_pct)}</span>
        </header>
        <div class="atributos">${atributos(f)}</div>
        <p class="ficha-texto">${esc(f.comentario)}</p>
        ${f.risco ? `<p class="ficha-risco"><strong>Risco:</strong> ${esc(f.risco)}</p>` : ""}
        ${f.fonte ? `<p class="ficha-fonte">Fonte: ${esc(f.fonte)}</p>` : ""}
      </article>`
    )
    .join("");
}

function metaDaAnalise(ia) {
  const meta = ia._meta || {};
  if (!meta.gerado_em) return "";
  const buscas = meta.buscas_web ? ` · ${meta.buscas_web} buscas` : "";
  return `${meta.modelo || ""} · effort ${meta.effort || "—"}${buscas} · ${dataHoraBR(meta.gerado_em)}`;
}

export function renderLeitura(ia, erro) {
  if (erro && !ia) {
    mostrar("#cartao-leitura", true);
    $("#ia-meta").textContent = "";
    $("#leitura").innerHTML = cartaoAlerta(
      "info",
      "Análise por IA não executada",
      esc(erro)
    );
    return;
  }
  if (!ia) {
    mostrar("#cartao-leitura", false);
    return;
  }

  const c = ia.carteira || {};
  const blocos = BLOCOS_LEITURA.filter(([, chave]) => c[chave])
    .map(
      ([titulo, chave]) =>
        `<div class="bloco-leitura"><div class="bloco-titulo">${titulo}</div><p>${esc(c[chave])}</p></div>`
    )
    .join("");

  const conclusao = c.conclusao
    ? `<div class="conclusao"><div class="bloco-titulo">Conclusão</div><p>${esc(c.conclusao)}</p></div>`
    : "";

  // Fatos, pontos de observação e contexto de mercado moram na Visão geral.
  const corpo = blocos + conclusao;

  // Sem nenhum bloco preenchido o cartão ficaria como uma moldura vazia.
  mostrar("#cartao-leitura", corpo !== "");
  $("#ia-meta").textContent = metaDaAnalise(ia);
  $("#leitura").innerHTML = corpo;
}

/** Mostra o aviso de tela vazia quando não há nem leitura nem fichas. */
export function renderAnaliseVazia() {
  const semConteudo =
    $("#cartao-leitura").classList.contains("hidden") &&
    $("#cartao-fichas").classList.contains("hidden");
  mostrar("#analise-vazia", semConteudo);
}

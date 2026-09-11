/** Tela "Configurações": perfil da carteira, limites de alerta e mensagem do Telegram. */

import { $, esc } from "./formato.js";
import { icone } from "./icones.js";

const CAMPOS = {
  "#c-fgc": "limite_fgc",
  "#c-venc": "alerta_vencimento_dias",
  "#c-conc": "alerta_concentracao_pct",
  "#c-prej": "alerta_prejuizo_pct",
  "#c-fatos": "max_fatos",
  "#c-opp": "max_oportunidades",
  "#c-execucoes": "max_execucoes",
};

const SEVERIDADES = [
  ["info", "informativa ou acima"],
  ["atencao", "atenção ou acima"],
  ["alerta", "só alerta"],
];

// Segue o weekday() do Python, que é quem lê a configuração: 0 = segunda.
const DIAS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];

/**
 * Os blocos da mensagem curta, na ordem em que aparecem nela.
 *
 * Espelha a tabela `BLOCOS` de `analise/gatilhos.py`. Cada bloco tem um
 * interruptor (pode aparecer?) e um ou mais limiares (merece aparecer hoje?);
 * um bloco novo é uma linha nova aqui, não um campo solto no HTML.
 *
 * Em cada campo, `rotulo` e `unidade` servem a duas saídas: o rótulo do
 * formulário sai como "Limiar (%)", no padrão do resto da tela, e a linha de
 * resumo do bloco recolhido sai como "limiar 3%". `curto` existe onde o rótulo
 * inteiro deixaria o resumo longo demais, e `curto: ""` onde o valor sozinho
 * já se explica.
 */
const BLOCOS = [
  {
    chave: "variacao_dia",
    rotulo: "Variação do dia",
    ajuda: "Entra só quando a carteira inteira anda mais que o limiar no dia.",
    campos: [{ nome: "limiar_pct", rotulo: "Limiar", unidade: "%", passo: "0.1" }],
  },
  {
    chave: "macro",
    rotulo: "Selic, CDI e IPCA",
    ajuda:
      "Compara com a leitura anterior e fala apenas quando o indicador muda. " +
      "É a única comparação com o passado da mensagem.",
    campos: [{ nome: "limiar_pp", rotulo: "Limiar", unidade: "p.p.", passo: "0.01" }],
  },
  {
    chave: "movimento",
    rotulo: "Posições em movimento",
    ajuda: "Uma posição pequena que oscila não vira notícia — daí o peso mínimo.",
    campos: [
      { nome: "limiar_pct", rotulo: "Limiar", unidade: "%", passo: "0.1" },
      {
        nome: "peso_minimo_pct",
        rotulo: "Peso mínimo",
        curto: "peso mín.",
        unidade: "%",
        passo: "0.1",
      },
      { nome: "max", rotulo: "Máximo de linhas", curto: "máx.", passo: "1" },
    ],
  },
  {
    chave: "calendario_rf",
    rotulo: "Cupons e vencimentos",
    ajuda:
      "Fala nos marcos de dias que faltam, e não todo dia da janela: 30, 15, 7, 3 e 1 " +
      "citam o vencimento cinco vezes, em dias distintos.",
    campos: [
      {
        nome: "marcos_dias",
        rotulo: "Marcos (dias)",
        curto: "marcos",
        tipo: "lista",
      },
      { nome: "max", rotulo: "Máximo de linhas", curto: "máx.", passo: "1" },
    ],
  },
  {
    chave: "alertas",
    rotulo: "Alertas do cálculo",
    ajuda:
      "Os que ficam abaixo do piso não somem: viram uma linha com a contagem de " +
      "alertas em curso.",
    campos: [
      {
        nome: "severidade_minima",
        rotulo: "Severidade mínima",
        curto: "severidade",
        tipo: "severidade",
      },
      { nome: "max", rotulo: "Máximo de linhas", curto: "máx.", passo: "1" },
    ],
  },
  {
    chave: "fatos_ia",
    rotulo: "Fatos levantados pela IA",
    ajuda: "Proventos, emissões e comunicados, filtrados pelo peso do ativo na carteira.",
    campos: [
      {
        nome: "severidade_minima",
        rotulo: "Severidade mínima",
        curto: "severidade",
        tipo: "severidade",
      },
      {
        nome: "peso_minimo_pct",
        rotulo: "Peso mínimo do ativo",
        curto: "peso mín.",
        unidade: "%",
        passo: "0.1",
      },
      { nome: "max", rotulo: "Máximo de linhas", curto: "máx.", passo: "1" },
    ],
  },
  {
    chave: "riscos_ia",
    rotulo: "Riscos levantados pela IA",
    ajuda: "Os riscos da leitura da carteira, do mais relevante para o menos.",
    campos: [
      {
        nome: "severidade_minima",
        rotulo: "Severidade mínima",
        curto: "severidade",
        tipo: "severidade",
      },
      { nome: "max", rotulo: "Máximo de linhas", curto: "máx.", passo: "1" },
    ],
  },
  {
    chave: "indicadores",
    rotulo: "Indicadores fora da faixa",
    ajuda: "P/VP e DY médios da renda variável, quando saem do que você aceita.",
    campos: [
      { nome: "p_vp_minimo", rotulo: "P/VP mínimo", curto: "P/VP mín.", passo: "0.01" },
      { nome: "p_vp_maximo", rotulo: "P/VP máximo", curto: "P/VP máx.", passo: "0.01" },
      { nome: "dy_minimo_pct", rotulo: "DY mínimo", curto: "DY mín.", unidade: "%", passo: "0.1" },
    ],
  },
  {
    chave: "aprofundamento",
    rotulo: "Ativo do dia",
    ajuda:
      "Rodízio escolhido pelo dia do ano: cicla a carteira inteira sem guardar nada. " +
      "É o primeiro a sair quando o dia tem muita notícia.",
    campos: [{ nome: "por_dia", rotulo: "Ativos por dia", passo: "1" }],
  },
  {
    chave: "resumo_ia",
    rotulo: "Resumo da IA",
    ajuda: "O sumário executivo da análise, nos dias da semana escolhidos.",
    campos: [
      { nome: "dias_semana", rotulo: "Dias da semana", curto: "às", tipo: "dias", largo: true },
    ],
  },
  {
    chave: "semanal",
    rotulo: "Fechamento semanal",
    ajuda:
      "Extremos acumulados e o que vence ou paga cupom nos próximos 30 dias, " +
      "uma vez por semana.",
    campos: [{ nome: "dia_semana", rotulo: "Dia da semana", curto: "às", tipo: "dia" }],
  },
];

// ─────────────────────────────────────────────
// Marcação
// ─────────────────────────────────────────────

const id = (chave, nome) => `tg-${chave}-${nome}`.replace(/_/g, "-");

/**
 * Um controle por tipo de campo, todos na classe `.campo` do resto da tela.
 *
 * Nada de componente próprio aqui: um número e um seletor têm de ter o mesmo
 * tamanho e o mesmo desenho nesta tela e em qualquer outra do sistema.
 */
const CONTROLES = {
  numero: (alvo, campo) => `<input id="${alvo}" type="number" step="${campo.passo}" min="0">`,
  lista: (alvo) => `<input id="${alvo}" placeholder="30, 15, 7, 3, 1">`,
  severidade: (alvo) =>
    `<select id="${alvo}">${SEVERIDADES.map(
      ([valor, rotulo]) => `<option value="${valor}">${rotulo}</option>`,
    ).join("")}</select>`,
  dia: (alvo) =>
    `<select id="${alvo}">${DIAS.map(
      (dia, i) => `<option value="${i}">${dia}</option>`,
    ).join("")}</select>`,
  dias: (alvo, campo) =>
    `<div class="dias-semana" id="${alvo}" role="group" aria-label="${esc(campo.rotulo)}">${DIAS.map(
      (dia, i) =>
        `<label class="dia-chip"><input type="checkbox" value="${i}"><span>${dia}</span></label>`,
    ).join("")}</div>`,
};

const rotuloDoCampo = (campo) =>
  campo.unidade ? `${campo.rotulo} (${campo.unidade})` : campo.rotulo;

function campoHtml(chave, campo) {
  const alvo = id(chave, campo.nome);
  const tipo = campo.tipo || "numero";
  // Os dias da semana são um grupo de caixas, não um controle único: um
  // `label for` apontando para o contêiner seria marcação inválida, então o
  // nome do campo vai no `aria-label` do próprio grupo.
  const rotulo =
    tipo === "dias"
      ? `<span class="rotulo-grupo">${esc(rotuloDoCampo(campo))}</span>`
      : `<label for="${alvo}">${esc(rotuloDoCampo(campo))}</label>`;
  return `<div class="campo${campo.largo ? " campo-largo" : ""}">
      ${rotulo}${CONTROLES[tipo](alvo, campo)}
    </div>`;
}

/**
 * Um bloco por linha recolhível: interruptor, nome e o resumo dos limiares.
 *
 * Vinte e cinco limiares abertos ao mesmo tempo competem entre si e não caberiam
 * na tela sem encolher os campos. Recolhidos, a decisão que importa — o bloco
 * entra ou não na mensagem — fica visível de relance, e o resumo abaixo do nome
 * poupa abrir o bloco só para conferir um valor.
 *
 * O interruptor é irmão do `<details>`, e não filho do `<summary>`: dentro dele,
 * clicar na caixa também abriria a dobra.
 *
 * O `name` compartilhado faz do conjunto um acordeão exclusivo — abrir um bloco
 * recolhe o anterior, sem JS —, o que mantém a altura da lista previsível por
 * mais blocos que existam. Recolher não perde nada: o `<details>` fechado só
 * esconde os campos, que continuam no DOM e são lidos por `coletarConfig`. Em
 * navegador que não suporte `name`, o acordeão simplesmente deixa de ser
 * exclusivo, e nada mais muda.
 */
function blocoHtml(bloco) {
  return `
    <div class="bloco-tg">
      <input type="checkbox" class="chave-bloco-tg" id="${id(bloco.chave, "ativo")}"
        aria-label="Incluir ${esc(bloco.rotulo)} na mensagem">
      <details name="tg-bloco" class="bloco-tg-dobra" data-bloco="${bloco.chave}">
        <summary>
          <span class="bloco-tg-nome">${esc(bloco.rotulo)}</span>
          <span class="bloco-tg-resumo" id="${id(bloco.chave, "resumo")}"></span>
          <span class="bloco-tg-seta">${icone("seta", 15)}</span>
        </summary>
        <p class="campo-dica">${esc(bloco.ajuda)}</p>
        <div class="grade-form">
          ${bloco.campos.map((campo) => campoHtml(bloco.chave, campo)).join("")}
        </div>
      </details>
    </div>`;
}

/** Desenha os blocos uma única vez, na carga da tela. */
export function montarTelegram() {
  const container = $("#tg-blocos");
  container.innerHTML = BLOCOS.map(blocoHtml).join("");
  // O resumo tem de acompanhar o que está sendo digitado: sem isto, recolher um
  // bloco recém-editado mostraria o valor antigo até salvar e recarregar.
  container.addEventListener("input", pintarResumos);
}

// ─────────────────────────────────────────────
// Resumo do bloco recolhido
// ─────────────────────────────────────────────

const rotuloDaOpcao = (lista, valor) =>
  (lista.find(([v]) => String(v) === String(valor)) || [])[1] || valor;

/** O valor de um campo como ele aparece na linha de resumo. */
function valorNoResumo(chave, campo) {
  const valor = lerCampo(chave, campo);
  if (campo.tipo === "dias") {
    return valor.length ? valor.map((i) => DIAS[i].toLowerCase()).join(", ") : "nenhum dia";
  }
  if (campo.tipo === "dia") return DIAS[Number(valor)].toLowerCase();
  if (campo.tipo === "severidade") return rotuloDaOpcao(SEVERIDADES, valor);
  if (campo.tipo === "lista") return valor;
  return `${String(valor).replace(".", ",")}${campo.unidade || ""}`;
}

/** "limiar 3% · peso mín. 3% · máx. 3" — os limiares do bloco, em uma linha. */
function resumoDoBloco(bloco) {
  return bloco.campos
    .map((campo) => {
      const nome = campo.curto ?? campo.rotulo.toLowerCase();
      return `${nome} ${valorNoResumo(bloco.chave, campo)}`.trim();
    })
    .join(" · ");
}

function pintarResumos() {
  for (const bloco of BLOCOS) {
    const alvo = $(`#${id(bloco.chave, "resumo")}`);
    if (alvo) alvo.textContent = resumoDoBloco(bloco);
  }
}

// ─────────────────────────────────────────────
// Leitura e escrita da tela
// ─────────────────────────────────────────────

function pintarCampo(chave, campo, valor) {
  const el = $(`#${id(chave, campo.nome)}`);
  if (campo.tipo === "dias") {
    const marcados = new Set((valor || []).map(Number));
    el.querySelectorAll("input").forEach((cx) => {
      cx.checked = marcados.has(Number(cx.value));
    });
    return;
  }
  el.value = campo.tipo === "lista" ? (valor || []).join(", ") : valor;
}

function lerCampo(chave, campo) {
  const el = $(`#${id(chave, campo.nome)}`);
  if (campo.tipo !== "dias") return el.value;
  return Array.from(el.querySelectorAll("input"))
    .filter((cx) => cx.checked)
    .map((cx) => Number(cx.value));
}

export function renderConfig(carteira) {
  $("#c-perfil").value = carteira.perfil || "";
  Object.entries(CAMPOS).forEach(([seletor, chave]) => {
    $(seletor).value = carteira.config[chave];
  });

  const telegram = carteira.config.telegram || {};
  $("#tg-max-itens").value = telegram.max_itens;
  $("#tg-so-relevante").checked = !!telegram.so_se_relevante;

  for (const bloco of BLOCOS) {
    const atual = telegram[bloco.chave] || {};
    $(`#${id(bloco.chave, "ativo")}`).checked = !!atual.ativo;
    bloco.campos.forEach((campo) => pintarCampo(bloco.chave, campo, atual[campo.nome]));
  }
  pintarResumos();
}

/** Lê a tela no formato que /api/config espera. */
export function coletarConfig() {
  const config = {};
  Object.entries(CAMPOS).forEach(([seletor, chave]) => {
    config[chave] = $(seletor).value;
  });

  const telegram = {
    max_itens: $("#tg-max-itens").value,
    so_se_relevante: $("#tg-so-relevante").checked,
  };
  for (const bloco of BLOCOS) {
    telegram[bloco.chave] = { ativo: $(`#${id(bloco.chave, "ativo")}`).checked };
    bloco.campos.forEach((campo) => {
      telegram[bloco.chave][campo.nome] = lerCampo(bloco.chave, campo);
    });
  }

  config.telegram = telegram;
  return { perfil: $("#c-perfil").value, config };
}

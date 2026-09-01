/* Portfolio Analyzer — interface local */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

let carteira = null;

// ── Utilitários ────────────────────────────

const moeda = (v) =>
  v == null ? "—" : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

const pct = (v, casas = 2, comSinal = true) =>
  v == null
    ? "—"
    : `${comSinal && v > 0 ? "+" : ""}${v.toFixed(casas).replace(".", ",")}%`;

const num = (v, casas = 2) =>
  v == null ? "—" : v.toFixed(casas).replace(".", ",");

const classeSinal = (v) => (v > 0 ? "pos" : v < 0 ? "neg" : "zero");

const dataBR = (iso) => {
  if (!iso) return "—";
  const [a, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${a}`;
};

const esc = (t) =>
  String(t ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])
  );

function toast(mensagem, tipo = "info", duracao = 4500) {
  const el = document.createElement("div");
  el.className = `toast toast-${tipo}`;
  el.textContent = mensagem;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), duracao);
}

async function api(rota, opcoes = {}) {
  const resp = await fetch(rota, {
    headers: { "Content-Type": "application/json" },
    ...opcoes,
  });
  const dados = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(dados.erro || `Erro ${resp.status}`);
  return dados;
}

const mostrar = (sel, visivel) => $(sel).classList.toggle("hidden", !visivel);

// ── Sumário executivo e indicadores ────────

function renderResumo(snapshot, ia, fundamentos) {
  const t = snapshot.totais;
  const saude = snapshot.saude_carteira;
  const rotulos = { otima: "Ótima", boa: "Boa", atencao: "Atenção", alerta: "Alerta" };

  $("#resumo-quando").textContent =
    "atualizado em " + new Date(snapshot.gerado_em).toLocaleString("pt-BR");

  $("#sumario").innerHTML = ia?.resumo
    ? `<p class="sumario-texto">${esc(ia.resumo)}</p>`
    : "";
  mostrar("#sumario", !!ia?.resumo);

  const tiles = [
    `<div class="stat">
       <div class="stat-label">Valor de mercado</div>
       <div class="stat-value">${moeda(t.valor_atual)}</div>
       <div class="stat-sub">custo ${moeda(t.valor_investido)}</div>
     </div>`,
    `<div class="stat">
       <div class="stat-label">Resultado acumulado</div>
       <div class="stat-value ${classeSinal(t.resultado)}">${moeda(t.resultado)}</div>
       <div class="stat-sub ${classeSinal(t.resultado)}">${pct(t.resultado_pct)}</div>
     </div>`,
  ];

  if (t.resultado_dia) {
    tiles.push(`<div class="stat">
       <div class="stat-label">Variação do dia</div>
       <div class="stat-value ${classeSinal(t.resultado_dia)}">${moeda(t.resultado_dia)}</div>
       <div class="stat-sub">renda variável</div>
     </div>`);
  }

  const m = fundamentos?.metricas;
  if (m?.p_vp_medio) {
    const leitura = m.p_vp_medio < 1 ? "desconto patrimonial" : "ágio patrimonial";
    tiles.push(`<div class="stat">
       <div class="stat-label">P/VP médio ponderado</div>
       <div class="stat-value">${num(m.p_vp_medio, 2)}</div>
       <div class="stat-sub">${leitura} · ${m.com_desconto} com desconto, ${m.com_agio} com ágio</div>
     </div>`);
  }
  if (m?.dy_medio_pct) {
    tiles.push(`<div class="stat">
       <div class="stat-label">DY médio ponderado</div>
       <div class="stat-value">${pct(m.dy_medio_pct, 2, false)}</div>
       <div class="stat-sub">cobertura ${m.dy_cobertura}</div>
     </div>`);
    tiles.push(`<div class="stat">
       <div class="stat-label">Renda estimada</div>
       <div class="stat-value">${moeda(m.renda_mensal_estimada)}</div>
       <div class="stat-sub">por mês · ${moeda(m.renda_anual_estimada)} ao ano</div>
     </div>`);
  }

  tiles.push(`<div class="stat">
     <div class="stat-label">Saúde</div>
     <div class="stat-value"><span class="badge badge-${saude}">${rotulos[saude] || saude}</span></div>
     <div class="stat-sub">${snapshot.alertas.length} alerta(s) · ${t.posicoes} posições</div>
   </div>`);

  $("#stats").innerHTML = tiles.join("");
}

// ── Alocação e concentrações ───────────────

function barrasGrupo(grupos, titulo) {
  if (!grupos?.length) return "";
  const itens = grupos
    .map((g) => {
      const risco = g.peso_pct > 50 && g.quantidade > 1;
      return `<div class="aloc-item">
        <div class="aloc-head">
          <span>${esc(g.nome)} ${risco ? '<span class="chip-risco">concentrado</span>' : ""}
            <span class="sub">${esc(g.ativos.join(", "))}</span></span>
          <span class="mono">${pct(g.peso_pct, 1, false)} · ${moeda(g.valor)}</span>
        </div>
        <div class="aloc-bar"><div class="aloc-fill fill-neutro" style="width:${g.peso_pct}%"></div></div>
      </div>`;
    })
    .join("");
  return `<div class="subgrupo"><div class="subgrupo-titulo">${titulo}</div>${itens}</div>`;
}

function renderAlocacao(snapshot, fundamentos) {
  const classes = Object.entries(snapshot.classes);
  if (!classes.length) {
    $("#alocacao").innerHTML = '<div class="vazio">Nenhuma posição cadastrada.</div>';
    return;
  }

  const porClasse = classes
    .map(
      ([chave, c]) => `
      <div class="aloc-item">
        <div class="aloc-head">
          <span><strong>${c.rotulo}</strong> <span class="sub">${c.posicoes} ativo(s)</span></span>
          <span class="mono">${pct(c.peso_pct, 1, false)} · ${moeda(c.valor_atual)}
            <span class="${classeSinal(c.resultado)}">${pct(c.resultado_pct, 1)}</span></span>
        </div>
        <div class="aloc-bar"><div class="aloc-fill fill-${chave}" style="width:${c.peso_pct}%"></div></div>
      </div>`
    )
    .join("");

  $("#alocacao").innerHTML =
    porClasse +
    (fundamentos
      ? barrasGrupo(fundamentos.por_classificacao, "Por classificação (renda variável)") +
        barrasGrupo(fundamentos.por_segmento, "Por segmento") +
        barrasGrupo(fundamentos.por_gestora, "Por gestora / emissor")
      : "");
}

// ── Riscos e alertas ───────────────────────

function renderRiscos(snapshot, ia) {
  const partes = [];

  if (snapshot.alertas.length) {
    partes.push('<div class="subgrupo-titulo">Detectados pelo cálculo da carteira</div>');
    partes.push(
      snapshot.alertas
        .map(
          (a) => `<div class="alerta alerta-${a.severidade}">
            <div class="alerta-titulo">${esc(a.titulo)}</div>
            <div class="alerta-desc">${esc(a.descricao)}</div>
          </div>`
        )
        .join("")
    );
  }

  if (ia?.riscos?.length) {
    partes.push(
      '<div class="subgrupo-titulo" style="margin-top:14px">Levantados na análise, por relevância</div>'
    );
    partes.push(
      ia.riscos
        .map(
          (r, i) => `<div class="alerta alerta-${r.severidade}">
            <div class="alerta-titulo"><span class="ordem">${i + 1}</span> ${esc(r.titulo)}
              ${r.ativos?.length ? `<span class="sub">${esc(r.ativos.join(", "))}</span>` : ""}</div>
            <div class="alerta-desc">${esc(r.descricao)}</div>
          </div>`
        )
        .join("")
    );
  }

  $("#riscos").innerHTML =
    partes.join("") ||
    '<div class="vazio">Nenhum risco sinalizado — vencimentos, concentração e FGC dentro dos limites.</div>';
}

// ── Tabela de posições ─────────────────────

function renderPosicoes(snapshot, fundamentos) {
  const posicoes = carteira?.posicoes || [];
  if (!posicoes.length) {
    $("#posicoes").innerHTML =
      '<div class="vazio">Nenhuma posição cadastrada. Clique em “+ Nova posição”.</div>';
    return;
  }

  const calc = {};
  (snapshot?.posicoes || []).forEach((p) => (calc[p.id] = p));
  const fichas = {};
  (fundamentos?.fichas || []).forEach((f) => (fichas[f.ticker] = f));

  const linhas = posicoes
    .map((p) => {
      const c = calc[p.id];
      const f = fichas[p.ticker];
      const rotuloTipo = { fii: "FII", acao: "AÇÃO", cdb: "CDB" }[p.tipo];

      let nome, detalhe, segmento, pvp, dy;
      if (p.tipo === "cdb") {
        nome = esc(p.banco);
        const venc = c?.vencido
          ? "<strong class='neg'>vencido</strong>"
          : c
          ? `vence em ${c.dias_para_vencer} dias`
          : `vence ${dataBR(p.data_vencimento)}`;
        detalhe = `${dataBR(p.data_vencimento)} · ${venc}${
          c ? ` · líquido ${moeda(c.valor_liquido)}` : ""
        }`;
        segmento = esc(p.nome?.replace(`CDB ${p.banco} `, "") || "CDB");
        pvp = dy = "—";
      } else {
        nome = esc(p.ticker);
        detalhe = c?.preco_atual
          ? `${p.quantidade} × ${moeda(c.preco_atual)} · PM ${moeda(p.preco_medio)}`
          : `${p.quantidade} cotas · PM ${moeda(p.preco_medio)}`;
        segmento = f ? esc(f.segmento) : "—";
        pvp = f?.p_vp ? num(f.p_vp, 2) : "—";
        dy = f?.dy_12m_pct ? pct(f.dy_12m_pct, 1, false) : "—";
      }

      const resultado = c
        ? `<span class="${classeSinal(c.resultado)}">${moeda(c.resultado)}<br>
             <span class="sub ${classeSinal(c.resultado)}">${pct(c.resultado_pct)}</span></span>`
        : "—";

      return `
        <tr>
          <td><span class="tag tag-${p.tipo}">${rotuloTipo}</span></td>
          <td>
            <strong>${nome}</strong>
            ${f?.nome ? `<div class="sub">${esc(f.nome)}</div>` : ""}
            <div class="sub">${detalhe}</div>
            ${p.observacao ? `<div class="sub">${esc(p.observacao)}</div>` : ""}
            ${c?.erro_cotacao ? '<div class="sub neg">cotação indisponível</div>' : ""}
          </td>
          <td>${segmento}${
            f?.gestora ? `<div class="sub">${esc(f.gestora)}</div>` : ""
          }</td>
          <td class="num mono">${pvp}</td>
          <td class="num mono">${dy}</td>
          <td class="num mono">${c ? moeda(c.valor_atual) : "—"}</td>
          <td class="num mono">${resultado}</td>
          <td class="num mono">${c ? pct(c.peso_pct, 1, false) : "—"}</td>
          <td class="num">
            <button class="btn-icon" data-editar="${p.id}" title="Editar">✎</button>
            <button class="btn-icon danger" data-excluir="${p.id}" title="Excluir">✕</button>
          </td>
        </tr>`;
    })
    .join("");

  $("#posicoes").innerHTML = `
    <div class="tabela-scroll">
      <table class="tabela">
        <thead><tr>
          <th>Tipo</th><th>Ativo</th><th>Segmento</th>
          <th class="num">P/VP</th><th class="num">DY 12M</th>
          <th class="num">Valor</th><th class="num">Resultado</th><th class="num">Peso</th><th></th>
        </tr></thead>
        <tbody>${linhas}</tbody>
      </table>
    </div>`;

  $$("[data-editar]").forEach((b) =>
    b.addEventListener("click", () => editarPosicao(b.dataset.editar))
  );
  $$("[data-excluir]").forEach((b) =>
    b.addEventListener("click", () => excluirPosicao(b.dataset.excluir))
  );
}

// ── Ficha por ativo ────────────────────────

function renderFichas(fundamentos) {
  if (!fundamentos?.fichas?.length) {
    mostrar("#card-fichas", false);
    return;
  }
  mostrar("#card-fichas", true);

  $("#fichas").innerHTML = fundamentos.fichas
    .map((f) => {
      const atributos = [
        ["Classificação", f.classificacao_rotulo],
        ["Segmento", f.segmento],
        ["Gestão", f.gestora],
        ["Patrimônio", f.patrimonio],
        ["P/VP", f.p_vp ? num(f.p_vp, 2) : null],
        ["DY 12m", f.dy_12m_pct ? pct(f.dy_12m_pct, 1, false) : null],
        ["Vacância", f.vacancia_pct ? pct(f.vacancia_pct, 1, false) : null],
        ["Peso", pct(f.peso_pct, 1, false)],
      ]
        .filter(([, v]) => v)
        .map(
          ([k, v]) =>
            `<div class="atributo"><span class="atributo-k">${k}</span><span class="atributo-v">${esc(v)}</span></div>`
        )
        .join("");

      return `<article class="ficha">
        <header class="ficha-head">
          <div>
            <span class="ficha-ticker">${esc(f.ticker)}</span>
            <span class="ficha-nome">${esc(f.nome)}</span>
          </div>
          <span class="mono ${classeSinal(f.resultado_pct)}">${pct(f.resultado_pct)}</span>
        </header>
        <div class="atributos">${atributos}</div>
        <p class="ficha-texto">${esc(f.comentario)}</p>
        ${f.risco ? `<p class="ficha-risco"><strong>Risco:</strong> ${esc(f.risco)}</p>` : ""}
        ${f.fonte ? `<p class="ficha-fonte">Fonte: ${esc(f.fonte)}</p>` : ""}
      </article>`;
    })
    .join("");
}

// ── Leitura da carteira ────────────────────

function renderLeitura(ia, erro) {
  if (erro && !ia) {
    mostrar("#card-leitura", true);
    $("#leitura").innerHTML = `<div class="alerta alerta-info">
      <div class="alerta-titulo">Análise por IA não executada</div>
      <div class="alerta-desc">${esc(erro)}</div></div>`;
    $("#ia-meta").textContent = "";
    return;
  }
  if (!ia) {
    mostrar("#card-leitura", false);
    return;
  }
  mostrar("#card-leitura", true);

  const meta = ia._meta || {};
  $("#ia-meta").textContent = meta.gerado_em
    ? `${meta.modelo || ""} · effort ${meta.effort || "—"}` +
      (meta.buscas_web ? ` · ${meta.buscas_web} buscas` : "") +
      ` · ${new Date(meta.gerado_em).toLocaleString("pt-BR")}`
    : "";

  const c = ia.carteira || {};
  const blocos = [
    ["Diversificação", c.diversificacao],
    ["Concentração setorial", c.concentracao_setorial],
    ["Concentração de gestor / emissor", c.concentracao_gestor],
    ["Valuation", c.valuation],
    ["Geração de renda", c.renda],
  ]
    .filter(([, v]) => v)
    .map(
      ([k, v]) => `<div class="bloco-leitura">
        <div class="bloco-titulo">${k}</div>
        <p>${esc(v)}</p>
      </div>`
    )
    .join("");

  const conclusao = c.conclusao
    ? `<div class="conclusao"><div class="bloco-titulo">Conclusão</div><p>${esc(c.conclusao)}</p></div>`
    : "";

  const fatos = ia.fatos?.length
    ? `<div class="subgrupo-titulo" style="margin-top:18px">Fatos recentes</div>` +
      ia.fatos
        .map(
          (f) => `<div class="alerta alerta-${f.severidade}">
            <div class="alerta-titulo">[${esc(f.ativo)}] ${esc(f.titulo)}</div>
            <div class="alerta-desc">${esc(f.descricao)}</div>
            ${f.fonte ? `<div class="alerta-fonte">Fonte: ${esc(f.fonte)}</div>` : ""}
          </div>`
        )
        .join("")
    : "";

  const oportunidades = ia.oportunidades?.length
    ? `<div class="subgrupo-titulo" style="margin-top:18px">Pontos de observação</div>` +
      ia.oportunidades
        .map(
          (o) => `<div class="alerta alerta-info">
            <div class="alerta-titulo">${esc(o.titulo)}
              ${o.ativos?.length ? `<span class="sub">${esc(o.ativos.join(", "))}</span>` : ""}</div>
            <div class="alerta-desc">${esc(o.descricao)}</div>
          </div>`
        )
        .join("")
    : "";

  const macro = ia.contexto_mercado
    ? `<div class="bloco-leitura" style="margin-top:18px">
         <div class="bloco-titulo">Contexto de mercado</div><p>${esc(ia.contexto_mercado)}</p>
       </div>`
    : "";

  $("#leitura").innerHTML = blocos + conclusao + fatos + oportunidades + macro;
}

// ── Indicadores macro ──────────────────────

function renderMacro(snapshot) {
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
        `<div class="macro-item"><span class="macro-k">${k}</span><span class="macro-v mono">${v}</span></div>`
    )
    .join("");
}

function renderConfig() {
  const c = carteira.config;
  $("#c-perfil").value = carteira.perfil || "";
  $("#c-fgc").value = c.limite_fgc;
  $("#c-venc").value = c.alerta_vencimento_dias;
  $("#c-conc").value = c.alerta_concentracao_pct;
  $("#c-prej").value = c.alerta_prejuizo_pct;
  $("#c-fatos").value = c.max_fatos;
  $("#c-opp").value = c.max_oportunidades;
}

function renderAnalise(resultado) {
  if (!resultado || resultado.vazio) return;
  const { snapshot, ia, ia_erro, fundamentos } = resultado;
  renderResumo(snapshot, ia, fundamentos);
  renderAlocacao(snapshot, fundamentos);
  renderRiscos(snapshot, ia);
  renderPosicoes(snapshot, fundamentos);
  renderFichas(fundamentos);
  renderLeitura(ia, ia_erro);
  renderMacro(snapshot);
}

// ── Formulário de posições ─────────────────

function alternarCampos() {
  const cdb = $("#f-tipo").value === "cdb";
  $$(".campo-rv").forEach((el) => el.classList.toggle("hidden", cdb));
  $$(".campo-rf").forEach((el) => el.classList.toggle("hidden", !cdb));
  atualizarRotuloTaxa();
}

function atualizarRotuloTaxa() {
  const rotulos = {
    CDI: "Taxa (% do CDI)",
    PRE: "Taxa (% a.a.)",
    IPCA: "Spread sobre IPCA (% a.a.)",
  };
  $("#f-taxa-label").textContent = rotulos[$("#f-indexador").value];
}

function abrirForm(posicao = null) {
  $("#form-posicao").classList.remove("hidden");
  $("#f-id").value = posicao?.id || "";

  if (posicao) {
    $("#f-tipo").value = posicao.tipo;
    $("#f-observacao").value = posicao.observacao || "";
    if (posicao.tipo === "cdb") {
      $("#f-banco").value = posicao.banco || "";
      $("#f-valor-inicial").value = posicao.valor_inicial ?? "";
      $("#f-indexador").value = posicao.indexador || "CDI";
      $("#f-taxa").value = posicao.taxa ?? "";
      $("#f-data-aplicacao").value = posicao.data_aplicacao || "";
      $("#f-data-vencimento").value = posicao.data_vencimento || "";
      $("#f-liquidez").checked = !!posicao.liquidez_diaria;
    } else {
      $("#f-ticker").value = posicao.ticker || "";
      $("#f-quantidade").value = posicao.quantidade ?? "";
      $("#f-preco-medio").value = posicao.preco_medio ?? "";
      $("#f-data-compra").value = posicao.data_compra || "";
    }
  }
  alternarCampos();
  $("#form-posicao").scrollIntoView({ behavior: "smooth", block: "center" });
}

function fecharForm() {
  $("#form-posicao").reset();
  $("#f-id").value = "";
  $("#form-posicao").classList.add("hidden");
}

function coletarForm() {
  const tipo = $("#f-tipo").value;
  const base = { tipo, observacao: $("#f-observacao").value };
  if (tipo === "cdb") {
    return {
      ...base,
      banco: $("#f-banco").value,
      valor_inicial: $("#f-valor-inicial").value,
      indexador: $("#f-indexador").value,
      taxa: $("#f-taxa").value,
      data_aplicacao: $("#f-data-aplicacao").value,
      data_vencimento: $("#f-data-vencimento").value,
      liquidez_diaria: $("#f-liquidez").checked,
    };
  }
  return {
    ...base,
    ticker: $("#f-ticker").value,
    quantidade: $("#f-quantidade").value,
    preco_medio: $("#f-preco-medio").value,
    data_compra: $("#f-data-compra").value,
  };
}

function editarPosicao(id) {
  const posicao = carteira.posicoes.find((p) => p.id === id);
  if (posicao) abrirForm(posicao);
}

async function excluirPosicao(id) {
  const posicao = carteira.posicoes.find((p) => p.id === id);
  const nome = posicao?.ticker || posicao?.nome || "esta posição";
  if (!confirm(`Excluir ${nome} da carteira?`)) return;
  try {
    await api(`/api/posicoes/${id}`, { method: "DELETE" });
    toast("Posição excluída.", "ok");
    await carregarCarteira();
  } catch (e) {
    toast(e.message, "erro");
  }
}

// ── Ações ──────────────────────────────────

async function carregarCarteira() {
  carteira = await api("/api/carteira");
  renderConfig();
  const ultima = await api("/api/analise");
  if (ultima.vazio) renderPosicoes(null, null);
  else renderAnalise(ultima);
}

async function rodarAnalise(comIA) {
  const botao = comIA ? $("#btn-analise") : $("#btn-analise-rapida");
  const original = botao.textContent;
  $$(".header-right .btn").forEach((b) => (b.disabled = true));
  botao.innerHTML = `<span class="spinner"></span>${comIA ? "Analisando…" : "Atualizando…"}`;
  if (comIA) toast("A análise consulta fontes na web e leva algum tempo.", "info", 9000);

  try {
    const resultado = await api(`/api/analise?ia=${comIA ? 1 : 0}`, { method: "POST" });
    renderAnalise(resultado);
    if (comIA && resultado.ia_erro) toast(resultado.ia_erro, "erro", 9000);
    else toast(comIA ? "Análise concluída." : "Cotações atualizadas.", "ok");
  } catch (e) {
    toast(e.message, "erro", 9000);
  } finally {
    $$(".header-right .btn").forEach((b) => (b.disabled = false));
    botao.textContent = original;
  }
}

// ── Inicialização ──────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
  $("#f-tipo").addEventListener("change", alternarCampos);
  $("#f-indexador").addEventListener("change", atualizarRotuloTaxa);
  $("#btn-nova").addEventListener("click", () => abrirForm());
  $("#btn-cancelar").addEventListener("click", fecharForm);
  $("#btn-analise").addEventListener("click", () => rodarAnalise(true));
  $("#btn-analise-rapida").addEventListener("click", () => rodarAnalise(false));

  $("#form-posicao").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const id = $("#f-id").value;
    try {
      await api(id ? `/api/posicoes/${id}` : "/api/posicoes", {
        method: id ? "PUT" : "POST",
        body: JSON.stringify(coletarForm()),
      });
      toast(id ? "Posição atualizada." : "Posição adicionada.", "ok");
      fecharForm();
      await carregarCarteira();
    } catch (e) {
      toast(e.message, "erro", 7000);
    }
  });

  $("#form-config").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      carteira = await api("/api/config", {
        method: "POST",
        body: JSON.stringify({
          perfil: $("#c-perfil").value,
          config: {
            limite_fgc: $("#c-fgc").value,
            alerta_vencimento_dias: $("#c-venc").value,
            alerta_concentracao_pct: $("#c-conc").value,
            alerta_prejuizo_pct: $("#c-prej").value,
            max_fatos: $("#c-fatos").value,
            max_oportunidades: $("#c-opp").value,
          },
        }),
      });
      toast("Parâmetros salvos.", "ok");
    } catch (e) {
      toast(e.message, "erro");
    }
  });

  $("#btn-telegram").addEventListener("click", async () => {
    try {
      await api("/api/telegram", { method: "POST" });
      toast("Relatório enviado ao Telegram.", "ok");
    } catch (e) {
      toast(e.message, "erro", 7000);
    }
  });

  try {
    const status = await api("/api/status");
    $("#status-ia").textContent = status.ia_disponivel
      ? `IA: ${status.modelo}`
      : "IA indisponível";
    $("#status-ia").title = status.ia_motivo || "";
    $("#btn-analise").disabled = !status.ia_disponivel;
    $("#btn-telegram").disabled = !status.telegram_configurado;
    if (!status.telegram_configurado)
      $("#btn-telegram").title = "Configure TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no .env";
    await carregarCarteira();
  } catch (e) {
    toast("Falha ao carregar: " + e.message, "erro", 9000);
  }
});

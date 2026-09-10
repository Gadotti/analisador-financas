/** Formatação de números, datas e texto para a interface. */

export const $ = (sel) => document.querySelector(sel);
export const $$ = (sel) => Array.from(document.querySelectorAll(sel));

export const moeda = (v) =>
  v == null ? "—" : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

/** Valor em reais sem os centavos — para rótulos de apoio e eixos de gráfico. */
export const moedaCurta = (v) =>
  v == null
    ? "—"
    : v.toLocaleString("pt-BR", {
        style: "currency",
        currency: "BRL",
        maximumFractionDigits: 0,
      });

export const pct = (v, casas = 2, comSinal = true) =>
  v == null
    ? "—"
    : `${comSinal && v > 0 ? "+" : ""}${v.toFixed(casas).replace(".", ",")}%`;

export const num = (v, casas = 2) =>
  v == null ? "—" : v.toFixed(casas).replace(".", ",");

export const classeSinal = (v) => (v > 0 ? "pos" : v < 0 ? "neg" : "zero");

/** Cor por classe de ativo — mesma régua na alocação e no resultado detalhado. */
export const COR_CLASSE = {
  fii: "var(--fii)",
  acao: "var(--acao)",
  cdb: "var(--cdb)",
  lci: "var(--lci)",
  lca: "var(--lca)",
  tesouro: "var(--tesouro)",
};
export const corClasse = (tipo) => COR_CLASSE[tipo] || "var(--t3)";

export function dataBR(iso) {
  if (!iso) return "—";
  const [ano, mes, dia] = iso.slice(0, 10).split("-");
  return `${dia}/${mes}/${ano}`;
}

/** Dia e mês, para o eixo do gráfico de histórico. */
export function diaMes(iso) {
  const [, mes, dia] = iso.slice(0, 10).split("-");
  return `${dia}/${mes}`;
}

export const dataHoraBR = (iso) => new Date(iso).toLocaleString("pt-BR");

export const esc = (t) =>
  String(t ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])
  );

export const mostrar = (sel, visivel) => $(sel).classList.toggle("hidden", !visivel);

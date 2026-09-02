/**
 * Ícones em SVG de traço, grade de 20px.
 *
 * São desenhados aqui em vez de virem de glifos de texto para que herdem a cor
 * do elemento e continuem nítidos em qualquer tamanho.
 */

const TRACOS = 'fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"';

const CAMINHOS = {
  visaoGeral:
    '<rect x="2.5" y="2.5" width="6" height="6" rx="1.5"></rect><rect x="11.5" y="2.5" width="6" height="6" rx="1.5"></rect><rect x="2.5" y="11.5" width="6" height="6" rx="1.5"></rect><rect x="11.5" y="11.5" width="6" height="6" rx="1.5"></rect>',
  posicoes:
    '<path d="M7 5h10M7 10h10M7 15h10"></path><circle cx="3.2" cy="5" r="1.1"></circle><circle cx="3.2" cy="10" r="1.1"></circle><circle cx="3.2" cy="15" r="1.1"></circle>',
  analise: '<path d="M2.5 13.5l4-4.5 3.5 3 7.5-8"></path><path d="M13 4h4.5v4.5"></path>',
  historico: '<circle cx="10" cy="10" r="7.5"></circle><path d="M10 5.5V10l3 2"></path>',
  configuracoes:
    '<circle cx="10" cy="10" r="2.6"></circle><path d="M10 2.5v2M10 15.5v2M17.5 10h-2M4.5 10h-2M15.3 4.7l-1.4 1.4M6.1 13.9l-1.4 1.4M15.3 15.3l-1.4-1.4M6.1 6.1L4.7 4.7"></path>',
  alerta: '<circle cx="10" cy="10" r="7.5"></circle><path d="M10 6.2v5M10 13.8v.2"></path>',
  atencao: '<path d="M10 3l7.5 13H2.5z"></path><path d="M10 8v3.5M10 14v.2"></path>',
  info: '<circle cx="10" cy="10" r="7.5"></circle><path d="M10 9v5M10 6.2v.2"></path>',
  escudo: '<path d="M10 2.5l6 2.4v5c0 4-2.6 6.6-6 8-3.4-1.4-6-4-6-8v-5z"></path><path d="M7.4 10.1l1.9 1.9 3.4-3.6"></path>',
  seta: '<path d="M5.5 8l4.5 4.5L14.5 8"></path>',
  editar: '<path d="M13.5 3.5l3 3L7 16H4v-3z"></path>',
  excluir: '<path d="M4 5.5h12M8.2 5.5V3.8h3.6v1.7M5.6 5.5l.8 10.7h7.2l.8-10.7"></path>',
};

/** SVG do ícone, pronto para injetar como HTML. */
export function icone(nome, tamanho = 18) {
  const caminho = CAMINHOS[nome];
  if (!caminho) throw new Error(`Ícone desconhecido: "${nome}". Conhecidos: ${Object.keys(CAMINHOS).join(", ")}`);
  return `<svg width="${tamanho}" height="${tamanho}" viewBox="0 0 20 20" ${TRACOS} aria-hidden="true">${caminho}</svg>`;
}

/** Ícone que representa a severidade de um alerta. */
export const iconeSeveridade = (severidade) =>
  icone({ alerta: "alerta", atencao: "atencao" }[severidade] || "info", 17);

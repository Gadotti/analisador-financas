/** Barra lateral e troca de tela. Nenhuma requisição: só mostra e esconde. */

import { $, $$ } from "./formato.js";
import { icone } from "./icones.js";

export const TELAS = [
  { id: "visao-geral", rotulo: "Visão geral", icone: "visaoGeral", subtitulo: "Onde a carteira está hoje" },
  { id: "posicoes", rotulo: "Posições", icone: "posicoes", subtitulo: "Cadastro e marcação a mercado" },
  { id: "analise", rotulo: "Análise", icone: "analise", subtitulo: "Fichas por ativo e leitura da IA" },
  { id: "equivalencia", rotulo: "Equivalência", icone: "balanca", subtitulo: "Quanto uma LCI isenta vale em CDB" },
  { id: "historico", rotulo: "Histórico", icone: "historico", subtitulo: "Evolução das execuções registradas" },
  { id: "configuracoes", rotulo: "Configurações", icone: "configuracoes", subtitulo: "Perfil e limites de alerta" },
];

const telaValida = (id) => TELAS.some((t) => t.id === id);

const telaDaUrl = () => {
  const id = location.hash.replace("#", "");
  return telaValida(id) ? id : TELAS[0].id;
};

function pintarSelecao(idAtivo) {
  const tela = TELAS.find((t) => t.id === idAtivo);
  $("#titulo-pagina").textContent = tela.rotulo;
  $("#subtitulo-pagina").textContent = tela.subtitulo;

  TELAS.forEach(({ id }) => {
    $(`#pg-${id}`).classList.toggle("hidden", id !== idAtivo);
    const item = $(`[data-tela="${id}"]`);
    if (idAtivo === id) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  });
}

/**
 * Monta a barra lateral e passa a reagir ao hash da URL.
 *
 * @param {(id: string) => void} aoTrocar Chamado após cada troca de tela.
 */
export function iniciarNavegacao(aoTrocar) {
  $("#nav").innerHTML = TELAS.map(
    (t) => `<button type="button" class="nav-item" data-tela="${t.id}">
      ${icone(t.icone)}<span>${t.rotulo}</span>
      <span class="nav-contagem mono" data-contagem="${t.id}"></span>
    </button>`
  ).join("");

  $$("[data-tela]").forEach((botao) =>
    botao.addEventListener("click", () => {
      location.hash = botao.dataset.tela;
    })
  );

  const aplicar = () => {
    const id = telaDaUrl();
    pintarSelecao(id);
    aoTrocar(id);
  };

  window.addEventListener("hashchange", aplicar);
  aplicar();
}

/** Número mostrado à direita de um item da barra lateral. */
export function definirContagem(idTela, valor) {
  const el = $(`[data-contagem="${idTela}"]`);
  if (el) el.textContent = valor ?? "";
}

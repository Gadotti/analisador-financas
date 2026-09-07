/** Tela "Configurações": perfil da carteira e limites de alerta. */

import { $ } from "./formato.js";

const CAMPOS = {
  "#c-fgc": "limite_fgc",
  "#c-venc": "alerta_vencimento_dias",
  "#c-conc": "alerta_concentracao_pct",
  "#c-prej": "alerta_prejuizo_pct",
  "#c-fatos": "max_fatos",
  "#c-opp": "max_oportunidades",
  "#c-execucoes": "max_execucoes",
};

export function renderConfig(carteira) {
  $("#c-perfil").value = carteira.perfil || "";
  Object.entries(CAMPOS).forEach(([seletor, chave]) => {
    $(seletor).value = carteira.config[chave];
  });
}

/** Lê a tela no formato que /api/config espera. */
export function coletarConfig() {
  const config = {};
  Object.entries(CAMPOS).forEach(([seletor, chave]) => {
    config[chave] = $(seletor).value;
  });
  return { perfil: $("#c-perfil").value, config };
}

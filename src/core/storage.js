/**
 * Leitura da última análise e do histórico diário.
 *
 * Quem grava esses arquivos é o script Python: aqui o Node apenas lê o que a
 * análise produziu, para servir à interface.
 */

import fs from "node:fs";
import path from "node:path";

import { historyDir, lastAnalysisFile } from "../config/paths.js";

export function ultimaAnalise() {
  try {
    return JSON.parse(fs.readFileSync(lastAnalysisFile(), "utf8"));
  } catch {
    return null;
  }
}

/** Série histórica do valor da carteira, da data mais antiga para a mais recente. */
export function historico(limite = 60) {
  let arquivos;
  try {
    arquivos = fs
      .readdirSync(historyDir())
      .filter((nome) => nome.endsWith(".json"))
      .sort();
  } catch {
    return [];
  }

  const serie = [];
  for (const nome of arquivos.slice(-limite)) {
    try {
      const dados = JSON.parse(fs.readFileSync(path.join(historyDir(), nome), "utf8"));
      const { totais } = dados.snapshot;
      serie.push({
        data: dados.snapshot.data,
        valor_investido: totais.valor_investido,
        valor_atual: totais.valor_atual,
        resultado: totais.resultado,
        resultado_pct: totais.resultado_pct,
        saude: dados.snapshot.saude_carteira,
      });
    } catch {
      // registro corrompido ou de outro formato: ignora
    }
  }
  return serie;
}

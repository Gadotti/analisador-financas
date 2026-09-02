/**
 * Leitura das variáveis de ambiente que a interface precisa exibir.
 *
 * São apenas checagens locais: quem de fato conversa com a API de IA e com o
 * Telegram é o script Python. O servidor só precisa saber se os botões devem
 * ficar habilitados e qual provedor e modelo aparecem no rodapé — tudo isso
 * declarado no .env (veja src/config/configIa.js).
 */

import { ConfiguracaoIaError, configuracaoIa } from "../config/configIa.js";

/** Descrição do provedor ativo, ou null quando o .env não a define. */
export function descricaoIa() {
  try {
    return configuracaoIa({ exigirChave: false });
  } catch (erro) {
    if (erro instanceof ConfiguracaoIaError) return null;
    throw erro;
  }
}

/** Modelo configurado para a análise por IA, ou null se não houver. */
export function modeloIa() {
  return descricaoIa()?.modelo ?? null;
}

/** Provedor configurado para a análise por IA, ou null se não houver. */
export function provedorIa() {
  return descricaoIa()?.provedor ?? null;
}

/** Indica se a análise por IA pode ser executada e o motivo em caso negativo. */
export function statusIa() {
  try {
    configuracaoIa();
  } catch (erro) {
    if (erro instanceof ConfiguracaoIaError) return { ok: false, motivo: erro.message };
    throw erro;
  }
  return { ok: true, motivo: "" };
}

export function telegramConfigurado() {
  return Boolean(process.env.TELEGRAM_BOT_TOKEN && process.env.TELEGRAM_CHAT_ID);
}

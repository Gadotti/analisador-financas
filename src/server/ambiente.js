/**
 * Leitura das variáveis de ambiente que a interface precisa exibir.
 *
 * São apenas checagens locais: quem de fato conversa com a Anthropic e com o
 * Telegram é o script Python. O servidor só precisa saber se os botões devem
 * ficar habilitados e qual modelo aparece no rodapé.
 */

export const MODELO_PADRAO = "claude-opus-5";

/** Modelo configurado para a análise por IA. */
export function modeloIa() {
  return process.env.ANTHROPIC_MODEL || MODELO_PADRAO;
}

/** Indica se a análise por IA pode ser executada e o motivo em caso negativo. */
export function statusIa() {
  if (!process.env.ANTHROPIC_API_KEY) {
    return { ok: false, motivo: "ANTHROPIC_API_KEY nao configurada (veja o arquivo .env)." };
  }
  return { ok: true, motivo: "" };
}

export function telegramConfigurado() {
  return Boolean(process.env.TELEGRAM_BOT_TOKEN && process.env.TELEGRAM_CHAT_ID);
}

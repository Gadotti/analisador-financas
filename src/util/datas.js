/**
 * Datas em UTC puro.
 *
 * Toda data do sistema é um "dia civil" (AAAA-MM-DD) sem hora. Representá-las
 * como meia-noite UTC evita que o fuso local desloque um dia na conversão.
 */

export const MS_DIA = 86_400_000;

/** Converte 'AAAA-MM-DD' em Date na meia-noite UTC. Lança se for inválida. */
export function paraData(iso) {
  const texto = String(iso ?? "").slice(0, 10);
  const casa = /^(\d{4})-(\d{2})-(\d{2})$/.exec(texto);
  if (!casa) throw new RangeError(`Data inválida: '${iso}'`);
  const [, ano, mes, dia] = casa.map(Number);
  const data = new Date(Date.UTC(ano, mes - 1, dia));
  if (
    data.getUTCFullYear() !== ano ||
    data.getUTCMonth() !== mes - 1 ||
    data.getUTCDate() !== dia
  ) {
    throw new RangeError(`Data inválida: '${iso}'`);
  }
  return data;
}

/** Date -> 'AAAA-MM-DD'. */
export function paraISO(data) {
  return data.toISOString().slice(0, 10);
}

/** Hoje, no calendário local, como Date UTC de meia-noite. */
export function hoje() {
  const agora = new Date();
  return new Date(Date.UTC(agora.getFullYear(), agora.getMonth(), agora.getDate()));
}

export function somarDias(data, dias) {
  return new Date(data.getTime() + dias * MS_DIA);
}

/** Diferença em dias corridos (b - a). */
export function diferencaDias(a, b) {
  return Math.round((b.getTime() - a.getTime()) / MS_DIA);
}

/** Data e hora local em ISO sem fuso, com precisão de segundos. */
export function agoraISO(data = new Date()) {
  const p = (n, casas = 2) => String(n).padStart(casas, "0");
  return (
    `${p(data.getFullYear(), 4)}-${p(data.getMonth() + 1)}-${p(data.getDate())}` +
    `T${p(data.getHours())}:${p(data.getMinutes())}:${p(data.getSeconds())}`
  );
}

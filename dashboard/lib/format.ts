const integer = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 });
const oneDecimal = new Intl.NumberFormat("es-CO", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export const int = (v: number) => integer.format(v);

export const pct = (v: number, digits = 0) =>
  `${new Intl.NumberFormat("es-CO", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(v * 100)} %`;

/** Pesos: "15,9 M" desde un millón, si no el número entero ("−14.487"). */
export function cop(v: number): string {
  const sign = v < 0 ? "−" : "";
  const a = Math.abs(v);
  return a >= 1e6 ? `${sign}${oneDecimal.format(a / 1e6)} M` : `${sign}${integer.format(a)}`;
}

export const signed = (v: number, f: (x: number) => string) => (v > 0 ? `+${f(v)}` : v < 0 ? f(v) : "sin cambio");

/** Siempre en millones: "0,6 M". */
export const copM = (v: number) => `${v < 0 ? "−" : ""}${oneDecimal.format(Math.abs(v) / 1e6)} M`;

// Formatos cortos para números y fechas (igual que en la app Streamlit).
export const pct = (x: number, d = 0) => `${(x * 100).toFixed(d)}%`;
export const num = (x: number, d = 2) => x.toFixed(d);
export const signed = (x: number, d = 2) => (x >= 0 ? "+" : "") + x.toFixed(d);
export const justa = (p: number) => (p > 0 ? (1 / p).toFixed(2) : "∞");
export const corto = (s: string, n = 12) => (s.length <= n ? s : s.slice(0, n - 1) + "…");
export const q = (x: number) => "Q" + Math.round(x).toLocaleString("es-GT");

export const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
/** "2026-09-17" -> "17/09/26" */
export const fechaCorta = (iso: string) => { const [y, m, d] = iso.split("-"); return `${d}/${m}/${y.slice(2)}`; };
/** "2026-09-17" -> "17/09/2026" */
export const fechaLarga = (iso: string) => { const [y, m, d] = iso.split("-"); return `${d}/${m}/${y}`; };
/** "2026-09-17" -> {dia: "17", mes: "sep"} */
export const diaMes = (iso: string) => { const [, m, d] = iso.split("-"); return { dia: d, mes: MESES[Number(m) - 1] }; };

/** Resumen del boleto en el navegador (mismas fórmulas que kuota.resumen_boleto). */
export function resumenLocal(legs: { prob: number; cuota: number; lo?: number; hi?: number }[]) {
  if (!legs.length) return null;
  const prod = (f: (l: (typeof legs)[number]) => number) => legs.reduce((a, l) => a * f(l), 1);
  const prob = prod((l) => l.prob), cuota = prod((l) => l.cuota), lo = prod((l) => l.lo ?? l.prob), hi = prod((l) => l.hi ?? l.prob);
  return { n: legs.length, prob, cuota, ev: prob * cuota - 1, lo, hi, ev_lo: lo * cuota - 1, ev_hi: hi * cuota - 1 };
}

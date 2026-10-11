// Formatos cortos para números y fechas (igual que en la app Streamlit).
export const pct = (x: number | null, d = 0) => x === null || !Number.isFinite(x) ? "No disponible" : `${(x * 100).toFixed(d)}%`;
export const num = (x: number | null | undefined, d = 2) => x == null || !Number.isFinite(x) ? "No disponible" : x.toFixed(d);
export const signed = (x: number | null, d = 2) => x === null || !Number.isFinite(x) ? "No disponible" : (x >= 0 ? "+" : "") + x.toFixed(d);
export const justa = (p: number, push = 0) => p > 0 ? num((1 - push) / p) : "No disponible";
export const corto = (s: string, n = 12) => (s.length <= n ? s : s.slice(0, n - 1) + "…");
export const q = (x: number) => "Q" + Math.round(x).toLocaleString("es-GT");

export const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
/** "2026-09-17" -> "17/09/26" */
export const fechaCorta = (iso: string) => { const [y, m, d] = iso.split("-"); return `${d}/${m}/${y.slice(2)}`; };
/** "2026-09-17" -> "17/09/2026" */
export const fechaLarga = (iso: string) => { const [y, m, d] = iso.split("-"); return `${d}/${m}/${y}`; };
/** "2026-09-17" -> {dia: "17", mes: "sep"} */
export const diaMes = (iso: string) => { const [, m, d] = iso.split("-"); return { dia: d, mes: MESES[Number(m) - 1] }; };

/** El navegador solo resume conteo/cuotas; probabilidades y EV los resuelve Python. */
export function resumenLocal(legs: { cuota: number }[]) {
  if (!legs.length) return null;
  return { n: legs.length, cuota: legs.reduce((a, l) => a * l.cuota, 1), prob: null, ev: null };
}

import type { Leg } from "./api";
export type EstadoGuardado = {
  liga: string;
  partidos: Record<string, { local: string; visitante: string }>;
  met: string;
  boleto: Leg[];
  banca: number;
};
/** Conserva kuota-v1 y las selecciones antiguas; descarta solo datos ilegibles. */
export function restaurar(
  raw: string | null,
  initial: EstadoGuardado,
  ligas: string[],
  metricas: string[],
): EstadoGuardado {
  if (!raw) return initial;
  try {
    const value = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value))
      return initial;
    const partidos: EstadoGuardado["partidos"] = {};
    for (const [liga, p] of Object.entries(value.partidos ?? {})) {
      if (
        ligas.includes(liga) &&
        p &&
        typeof p === "object" &&
        "local" in p &&
        "visitante" in p &&
        typeof p.local === "string" &&
        typeof p.visitante === "string"
      )
        partidos[liga] = { local: p.local, visitante: p.visitante };
    }
    const boleto = Array.isArray(value.boleto)
      ? value.boleto.filter(
          (l: Leg) =>
            l &&
            typeof l === "object" &&
            [l.partido, l.metrica, l.mercado].every(
              (v) => typeof v === "string",
            ) &&
            Number.isFinite(l.cuota) &&
            l.cuota > 1 &&
            Number.isFinite(l.prob),
        )
      : initial.boleto;
    return {
      liga: ligas.includes(value.liga) ? value.liga : initial.liga,
      met: metricas.includes(value.met) ? value.met : initial.met,
      partidos,
      boleto,
      banca:
        Number.isFinite(value.banca) && value.banca > 0
          ? value.banca
          : initial.banca,
    };
  } catch {
    return initial;
  }
}

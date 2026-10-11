import type { Leg, Seleccion } from "./api";
function canonical(value: unknown): string {
  if (Array.isArray(value))
    return JSON.stringify(value.map((v) => JSON.parse(canonical(v))));
  if (value && typeof value === "object")
    return JSON.stringify(
      Object.fromEntries(
        Object.entries(value)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([k, v]) => [k, JSON.parse(canonical(v))]),
      ),
    );
  return JSON.stringify(value);
}
export function identidadSeleccion(s: Seleccion | undefined) {
  return s ? canonical(s) : null;
}
export function gruposBoleto(legs: Leg[]) {
  const groups = new Map<
    string,
    {
      nombre: string;
      liga?: string;
      local?: string;
      visitante?: string;
      legs: { leg: Leg; index: number }[];
    }
  >();
  legs.forEach((leg, index) => {
    const s = leg.seleccion;
    const key = s
      ? JSON.stringify([s.liga, s.local, s.visitante])
      : leg.partido;
    if (!groups.has(key))
      groups.set(key, {
        nombre: leg.partido,
        liga: s?.liga,
        local: s?.local,
        visitante: s?.visitante,
        legs: [],
      });
    groups.get(key)!.legs.push({ leg, index });
  });
  return [...groups.values()];
}

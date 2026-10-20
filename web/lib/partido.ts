"use client";
// Datos de la pantalla de partido. Pide primero la métrica que estás viendo y después,
// en segundo plano, las otras 8. Así cambiar de métrica no espera al servidor.
import { useEffect, useState } from "react";
import { api, METRICAS, type Cfg, type Seleccion } from "./api";

/** Un mercado tal como lo manda la API en modo=compacto (kuota.COMPACTO). */
export type MercadoCorto = {
  mercado: string;
  grupo: string;
  prob: number;
  push: number;
  justa: number | null;
  lo: number;
  hi: number;
  hl: number;
  nl: number;
  hv: number;
  nv: number;
  cal: string;
  cls: string;
  tag: string;
  ventaja?: "probada" | "sin ventaja" | "sin probar";
  seleccion: Seleccion;
};
export type Compacto = {
  liga: string;
  nombre_liga: string;
  partido: string;
  metrica: string;
  local: string;
  visitante: string;
  lambda_local: number;
  lambda_visitante: number;
  medias_liga: { local: number; visitante: number; total: number };
  cfg: Cfg;
  grupos: string[];
  n: number;
  filtro: string;
  mercados: MercadoCorto[];
  data_version: string;
};
export type Filtro = "Todos" | "Como jugarán";
export type Base = {
  liga: string;
  local: string;
  visitante: string;
  n: number;
  filtro: Filtro;
};

const cache = new Map<string, Compacto>();
function guardar(k: string, v: Compacto) {
  cache.delete(k);
  cache.set(k, v);
  if (cache.size > 150) cache.delete(cache.keys().next().value!);
}
const clave = (b: Base, met: string, cfg?: Cfg) =>
  JSON.stringify([b.liga, b.local, b.visitante, b.n, b.filtro, met, cfg ?? null]);

export function usePartidoRapido(
  base: Base | null,
  met: string,
  cfgs: Record<string, Cfg>,
) {
  const [, setRev] = useState(0);
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [intento, setIntento] = useState(0);
  const baseKey = base ? JSON.stringify(base) : "";
  const cfgsKey = JSON.stringify(cfgs);
  useEffect(() => {
    if (!base) return;
    const ctrl = new AbortController();
    const orden = [met, ...Object.keys(METRICAS).filter((m) => m !== met)];
    (async () => {
      for (const m of orden) {
        const k = clave(base, m, cfgs[m]);
        if (cache.has(k)) continue;
        try {
          const d = await api<Compacto>(
            `/liga/${base.liga}/partido`,
            {
              local: base.local,
              visitante: base.visitante,
              met: m,
              n: base.n,
              filtro: base.filtro,
              modo: "compacto",
              cfg: cfgs[m] ? JSON.stringify(cfgs[m]) : undefined,
            },
            ctrl.signal,
          );
          guardar(k, d);
          setRev((r) => r + 1);
        } catch (e) {
          if (ctrl.signal.aborted) return;
          if (m === met) {
            setErrores((p) => ({ ...p, [k]: (e as Error).message }));
            return;
          }
        }
      }
    })();
    return () => ctrl.abort();
    // baseKey y cfgsKey resumen base y cfgs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseKey, met, cfgsKey, intento]);
  const k = base ? clave(base, met, cfgs[met]) : "";
  return {
    data: (k && cache.get(k)) || null,
    error: (k && errores[k]) || null,
    reintentar: () => {
      setErrores({});
      setIntento((i) => i + 1);
    },
  };
}

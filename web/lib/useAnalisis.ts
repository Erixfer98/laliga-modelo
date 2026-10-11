"use client";
import { useEffect, useState } from "react";
import { useApi } from "./useApi";
import type { Pata, VistaPartido } from "./api";
type Resumen = Omit<
  VistaPartido,
  "pata" | "contexto_armar" | "contexto_analizar"
> & { data_version: string };
export function useAnalisis(
  path: string | null,
  params: {
    local: string;
    visitante: string;
    met: string;
    n: number;
    filtro: string;
    cfg?: string;
  },
  grupo?: string,
  seleccion?: string,
) {
  const contexto = JSON.stringify([
    path,
    params.local,
    params.visitante,
    params.met,
  ]);
  const [lineas, setLineas] = useState({ contexto, cfg: params.cfg });
  useEffect(() => {
    if (lineas.contexto !== contexto) {
      setLineas({ contexto, cfg: params.cfg });
      return;
    }
    const timer = setTimeout(
      () => setLineas({ contexto, cfg: params.cfg }),
      120,
    );
    return () => clearTimeout(timer);
    // El contexto y cfg identifican el ajuste; evita peticiones intermedias.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contexto, params.cfg]);
  const cfg = lineas.contexto === contexto ? lineas.cfg : params.cfg;
  const lineasPendientes = cfg !== params.cfg;
  const base = useApi<Resumen>(
    path,
    { ...params, cfg, modo: "resumen" },
    {
      cache: true,
      scope: contexto,
    },
  );
  const v = base.data;
  const g = grupo && v?.grupos.includes(grupo) ? grupo : v?.grupos[0];
  const mercado =
    v?.mercados.find((m) => m.mercado === seleccion) ??
    v?.mercados.find((m) => m.grupo === g);
  const detalle = useApi<Pata & { data_version: string }>(
    v && mercado && !base.loading && !lineasPendientes ? path : null,
    {
      ...params,
      cfg,
      modo: "detalle",
      pata: mercado?.mercado,
      data_version: v?.data_version,
    },
    { cache: true },
  );
  const p =
    detalle.data?.data_version === v?.data_version &&
    detalle.data?.mercado === mercado?.mercado
      ? detalle.data
      : null;
  return {
    ...base,
    loading: base.loading || lineasPendientes,
    v,
    mercado,
    p,
    detalle,
    grupo: g,
  };
}

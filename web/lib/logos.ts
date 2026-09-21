"use client";
// Escudos de equipos y logos de ligas (datos/logos.json vía /logos). Se piden una sola vez y se comparten.
import { useEffect, useState } from "react";
import { api } from "./api";

export type Logos = { ligas: Record<string, { nombre: string; logo: string }>; equipos: Record<string, Record<string, string>> };
const VACIO: Logos = { ligas: {}, equipos: {} };
let cache: Logos | null = null;
let pendiente: Promise<Logos> | null = null;

export function useLogos(): Logos {
  const [l, setL] = useState<Logos>(cache ?? VACIO);
  useEffect(() => {
    if (cache) { setL(cache); return; }
    pendiente ??= api<Logos>("/logos").then((d) => (cache = d)).catch(() => VACIO);
    let vivo = true;
    pendiente.then((d) => { if (vivo) setL(d); });
    return () => { vivo = false; };
  }, []);
  return l;
}

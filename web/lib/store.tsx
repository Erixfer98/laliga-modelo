"use client";
// Memoria del navegador: liga elegida, partido por liga, métrica, boleto y banca.
// Se guarda en localStorage (solo en este dispositivo). Cuando haya login, esto pasa a la base de datos del usuario.
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { Leg } from "./api";

type Partido = { local: string; visitante: string };
type State = { liga: string; partidos: Record<string, Partido>; met: string; boleto: Leg[]; banca: number };
const INICIAL: State = { liga: "laliga", partidos: {}, met: "goles", boleto: [], banca: 1000 };
const CLAVE = "kuota-v1";

type Store = State & {
  listo: boolean;
  setLiga: (liga: string) => void;
  setPartido: (liga: string, p: Partido) => void;
  setMet: (met: string) => void;
  addLeg: (leg: Leg) => void;
  removeLeg: (i: number) => void;
  vaciar: () => void;
  setBanca: (banca: number) => void;
};

const Ctx = createContext<Store | null>(null);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [s, setS] = useState<State>(INICIAL);
  const [listo, setListo] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(CLAVE);
      if (raw) setS({ ...INICIAL, ...JSON.parse(raw) });
    } catch { /* sin localStorage: se usa lo de defecto */ }
    setListo(true);
  }, []);

  useEffect(() => {
    if (!listo) return;
    try { localStorage.setItem(CLAVE, JSON.stringify(s)); } catch { /* ignorar */ }
  }, [s, listo]);

  const store: Store = {
    ...s, listo,
    setLiga: (liga) => setS((p) => ({ ...p, liga })),
    setPartido: (liga, partido) => setS((p) => ({ ...p, partidos: { ...p.partidos, [liga]: partido } })),
    setMet: (met) => setS((p) => ({ ...p, met })),
    addLeg: (leg) => setS((p) => ({ ...p, boleto: [...p.boleto, leg] })),
    removeLeg: (i) => setS((p) => ({ ...p, boleto: p.boleto.filter((_, j) => j !== i) })),
    vaciar: () => setS((p) => ({ ...p, boleto: [] })),
    setBanca: (banca) => setS((p) => ({ ...p, banca })),
  };
  return <Ctx.Provider value={store}>{children}</Ctx.Provider>;
}

export function useStore() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useStore fuera de StoreProvider");
  return c;
}

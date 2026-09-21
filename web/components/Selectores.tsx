"use client";
// Cabecera de partido estilo app: escudo + nombre de cada equipo; tocas un equipo para cambiarlo.
import { useEffect, useState } from "react";
import { api, LIGAS, type VistaInicio } from "@/lib/api";
import { useStore } from "@/lib/store";
import { Crest, LigaLogo } from "./Crest";

const cacheEquipos: Record<string, string[]> = {};

/** Lista de equipos de la liga (se pide una vez por liga). */
export function useEquipos(liga: string) {
  const [eq, setEq] = useState<{ liga: string; equipos: string[] }>({ liga, equipos: cacheEquipos[liga] ?? [] });
  useEffect(() => {
    if (cacheEquipos[liga]) { setEq({ liga, equipos: cacheEquipos[liga] }); return; }
    let vivo = true;
    api<VistaInicio>(`/liga/${liga}`).then((v) => { cacheEquipos[liga] = v.equipos; if (vivo) setEq({ liga, equipos: v.equipos }); }).catch(() => {});
    return () => { vivo = false; };
  }, [liga]);
  return eq.liga === liga ? eq.equipos : cacheEquipos[liga] ?? [];
}

/** Partido vigente de la liga (guardado o el de defecto) y cómo cambiarlo. */
export function usePartido() {
  const { liga, partidos, setPartido } = useStore();
  const equipos = useEquipos(liga);
  const g = partidos[liga];
  const local = g?.local && equipos.includes(g.local) ? g.local : equipos.includes("Real Madrid") ? "Real Madrid" : equipos[0] ?? "";
  const otros = equipos.filter((e) => e !== local);
  const visitante = g?.visitante && otros.includes(g.visitante) ? g.visitante : otros[0] ?? "";
  return {
    equipos, local, visitante, listo: equipos.length > 1,
    setLocal: (l: string) => setPartido(liga, { local: l, visitante: l === visitante ? equipos.find((e) => e !== l) ?? "" : visitante }),
    setVisitante: (v: string) => setPartido(liga, { local, visitante: v }),
  };
}

function Equipo({ liga, nombre, lado, opciones, onChange }: { liga: string; nombre: string; lado: "l" | "v"; opciones: string[]; onChange: (v: string) => void }) {
  return (
    <label className="relative flex-1 flex flex-col items-center gap-2 cursor-pointer min-w-0">
      <Crest liga={liga} equipo={nombre} size={64} lado={lado} className="shadow-[0_8px_24px_rgba(0,0,0,.35)]" />
      <span className="text-[0.95rem] font-extrabold text-center leading-tight px-1">{nombre}</span>
      <span className={`text-[0.66rem] font-bold uppercase tracking-[0.08em] ${lado === "l" ? "text-acc" : "text-vis"}`}>{lado === "l" ? "Local" : "Visitante"} ▾</span>
      <select className="absolute inset-0 w-full h-full opacity-0 cursor-pointer" value={nombre} onChange={(e) => onChange(e.target.value)} aria-label={lado === "l" ? "Local" : "Visitante"}>
        {opciones.map((e) => <option key={e} value={e}>{e}</option>)}
      </select>
    </label>
  );
}

export function CabeceraPartido({ sub }: { sub?: React.ReactNode }) {
  const { liga } = useStore();
  const { equipos, local, visitante, setLocal, setVisitante } = usePartido();
  return (
    <section className="hero rounded-card px-3 pt-4 pb-3 my-2.5">
      <div className="flex items-start gap-2">
        <Equipo liga={liga} nombre={local} lado="l" opciones={equipos} onChange={setLocal} />
        <div className="flex flex-col items-center pt-4 w-14 shrink-0">
          <span className="num text-[1.4rem] text-mut2">vs</span>
        </div>
        <Equipo liga={liga} nombre={visitante} lado="v" opciones={equipos.filter((e) => e !== local)} onChange={setVisitante} />
      </div>
      <div className="flex items-center justify-center gap-2 mt-3 text-[0.76rem] font-bold text-mut">
        <LigaLogo liga={liga} size={18} /> {LIGAS[liga]}{sub && <span className="text-mut2">· {sub}</span>}
      </div>
    </section>
  );
}

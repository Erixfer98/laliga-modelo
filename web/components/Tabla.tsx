"use client";
// Tabla de posiciones estilo app: escudo, franja de zona (Champions / Europa / descenso), forma de los últimos partidos.
import type { ReactNode } from "react";
import type { FilaTabla } from "@/lib/api";
import { Crest } from "./Crest";
import { Nota } from "./ui";

export function Forma({ forma, n = 5, chica }: { forma: string[]; n?: number; chica?: boolean }) {
  return (
    <span className={`inline-flex align-middle ${chica ? "gap-[2px]" : "gap-[3px]"}`}>
      {forma.slice(-n).map((x, i) => (
        <span key={i} className={`rounded-full font-extrabold text-white inline-flex items-center justify-center
          ${chica ? "w-[15px] h-[15px] text-[0.54rem]" : "w-[19px] h-[19px] text-[0.62rem]"}
          ${x === "g" ? "bg-ok" : x === "p" ? "bg-bad" : "bg-[#6b7280]"}`}>{x.toUpperCase()}</span>
      ))}
    </span>
  );
}

function Col({ children, w = "w-[20px] sm:w-[26px]", cls = "" }: { children: ReactNode; w?: string; cls?: string }) {
  return <div className={`${w} text-center text-mut shrink-0 ${cls}`}>{children}</div>;
}

export function TablaPosiciones({ liga, filas, compacta, resaltar = [] }: { liga: string; filas: FilaTabla[]; compacta?: boolean; resaltar?: string[] }) {
  const n = filas.length;
  return (
    <>
      <div className="flex items-center gap-1.5 sm:gap-2 py-1 text-[0.68rem] text-mut2 font-bold uppercase tracking-[0.05em]">
        <div className="w-[3px] shrink-0" /><div className="w-[18px] shrink-0" /><div className="w-[28px] shrink-0" /><div className="flex-1">Equipo</div>
        <Col>J</Col><Col cls="hidden sm:block">G</Col><Col cls="hidden sm:block">E</Col><Col cls="hidden sm:block">P</Col>
        {!compacta && <Col w="w-[44px]" cls="hidden sm:block">GF-GC</Col>}
        <Col>DG</Col><Col w="w-[26px] sm:w-[30px]" cls="text-right! text-txt">Pts</Col>
        {!compacta && <div className="w-[52px] sm:w-[102px] shrink-0" />}
      </div>
      {filas.map((f, i) => {
        const pos = i + 1;
        const zona = pos <= 4 ? "bg-ok" : pos <= 6 ? "bg-warn" : pos > n - 3 ? "bg-bad" : "bg-transparent";
        return (
          <div key={f.equipo} className={`flex items-center gap-1.5 sm:gap-2 py-2 border-b border-line2 last:border-b-0 text-[0.82rem] sm:text-[0.86rem] ${resaltar.includes(f.equipo) ? "bg-card2 rounded-xl" : ""}`}>
            <div className={`w-[3px] h-[28px] rounded-sm shrink-0 ${zona}`} />
            <div className="w-[18px] text-center text-mut font-bold shrink-0">{pos}</div>
            <Crest liga={liga} equipo={f.equipo} size={28} />
            <div className="flex-1 font-bold truncate min-w-0">{f.equipo}</div>
            <Col>{f.J}</Col><Col cls="hidden sm:block">{f.G}</Col><Col cls="hidden sm:block">{f.E}</Col><Col cls="hidden sm:block">{f.P}</Col>
            {!compacta && <Col w="w-[44px]" cls="hidden sm:block">{f.GF}-{f.GC}</Col>}
            <Col>{f.DG > 0 ? `+${f.DG}` : f.DG}</Col>
            <div className="w-[26px] sm:w-[30px] text-right font-extrabold shrink-0">{f.PTS}</div>
            {!compacta && (
              <div className="w-[52px] sm:w-[102px] shrink-0 text-right">
                <span className="sm:hidden"><Forma forma={f.forma} n={3} chica /></span>
                <span className="hidden sm:inline"><Forma forma={f.forma} /></span>
              </div>
            )}
          </div>
        );
      })}
      <Nota>J = jugados · DG = diferencia de goles · Pts = puntos. Franja verde = Champions · ámbar = Europa · roja = descenso (orientativo). Forma: antiguo → reciente. En celular se ocultan G/E/P{compacta ? "" : " y se muestran los últimos 3"}.</Nota>
    </>
  );
}

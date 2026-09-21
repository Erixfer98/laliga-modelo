"use client";
// Gráficos hechos con divs (sin librerías): barras partido a partido, matriz de marcadores y distribuciones Poisson.
import type { Grafico, Hist } from "@/lib/api";
import { pct } from "@/lib/fmt";
import { Nota } from "./ui";

/** Barras partido a partido (antiguo → reciente). Línea punteada blanca = línea del mercado; naranja = media de la liga. */
export function BarrasPartidos({ h, col, linea, mediaLiga, ok, color, sinLinea }: {
  h: Hist[]; col: "a_favor" | "en_contra" | "total"; linea: number; mediaLiga: number; ok: boolean[]; color: string; sinLinea?: boolean;
}) {
  if (!h.length) return <div className="text-[0.8rem] text-mut">sin partidos con ese filtro</div>;
  const filas = h.map((g, i) => ({ g, ok: ok[i] })).reverse();
  const mx = Math.max(...filas.map((f) => f.g[col]), linea, mediaLiga, 1) * 1.15;
  return (
    <div className="relative h-[110px] mt-6 mb-5">
      <div className="flex items-end gap-[3px] h-full">
        {filas.map(({ g, ok: cumple }, i) => (
          <div key={i} className="flex-1 min-w-[6px] rounded-t relative" title={`${g.rival} ${g.fecha}`}
            style={{ height: `${Math.max((g[col] / mx) * 100, 2)}%`, background: cumple ? color : "var(--miss)" }}>
            <span className="absolute -top-4 inset-x-0 text-center text-[0.66rem]">{g[col]}</span>
            <span className="absolute -bottom-4 inset-x-0 text-center text-[0.62rem] text-mut">{g.condicion === "Casa" ? "C" : "F"}</span>
          </div>
        ))}
      </div>
      {!sinLinea && (
        <div className="absolute inset-x-0 border-t-2 border-dashed border-mark opacity-80" style={{ bottom: `${(linea / mx) * 100}%` }}>
          <span className="absolute right-0 -top-3.5 text-[0.66rem]">línea {linea.toFixed(1)}</span>
        </div>
      )}
      <div className="absolute inset-x-0 border-t-2 border-dotted border-warn opacity-90" style={{ bottom: `${(mediaLiga / mx) * 100}%` }}>
        <span className="absolute left-0 -top-3.5 text-[0.66rem] text-warn">liga {mediaLiga.toFixed(1)}</span>
      </div>
    </div>
  );
}

/** Matriz de marcadores exactos: filas = local, columnas = visitante. Verde = marcadores con los que gana la pata. */
export function Matriz({ g, local, visitante }: { g: Extract<Grafico, { tipo: "matriz" }>; local: string; visitante: string }) {
  return (
    <>
      <table className="w-full border-separate border-spacing-[3px] text-[0.78rem]">
        <thead><tr><th></th>{Array.from({ length: g.k }, (_, y) => <th key={y} className="text-[0.72rem] text-mut2 font-medium p-0.5">{y}</th>)}</tr></thead>
        <tbody>
          {g.celdas.map((fila, x) => (
            <tr key={x}>
              <th className="text-[0.72rem] text-mut2 font-medium p-0.5">{x}</th>
              {fila.map((c, y) => {
                const a = 0.15 + 0.85 * (c.p / g.max);
                return <td key={y} className="text-center py-1.5 rounded-md" style={{ background: c.gana ? `rgba(46,158,91,${a.toFixed(2)})` : `rgba(120,130,150,${(a * 0.6).toFixed(2)})` }}>{Math.round(c.p * 100)}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <Nota>Filas = {local} · columnas = {visitante}. Cada celda es el % de ese marcador exacto según Poisson. Verde = marcadores con los que gana la pata; más intenso = más probable.</Nota>
    </>
  );
}

/** Barras de probabilidad por cantidad (distribución) o por diferencia local − visitante. */
export function BarrasPoisson({ valores, signo, nota }: { valores: { x: number; p: number; gana: boolean }[]; signo?: boolean; nota: string }) {
  const mx = Math.max(...valores.map((v) => v.p));
  return (
    <>
      <div className="relative h-[110px] mt-6 mb-5">
        <div className="flex items-end gap-[3px] h-full">
          {valores.map((v) => (
            <div key={v.x} className="flex-1 min-w-[6px] rounded-t relative" style={{ height: `${Math.max((v.p / mx) * 100, 2)}%`, background: v.gana ? "#2e9e5b" : "var(--miss)" }}>
              <span className="absolute -top-4 inset-x-0 text-center text-[0.66rem]">{pct(v.p)}</span>
              <span className="absolute -bottom-4 inset-x-0 text-center text-[0.62rem] text-mut">{signo && v.x > 0 ? `+${v.x}` : v.x}</span>
            </div>
          ))}
        </div>
      </div>
      <Nota>{nota}</Nota>
    </>
  );
}

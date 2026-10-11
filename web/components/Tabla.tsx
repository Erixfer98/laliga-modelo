"use client";
import type { FilaTabla } from "@/lib/api";
import { Crest } from "./Crest";
import { Nota } from "./ui";
export function Forma({
  forma,
  n = 5,
  chica,
}: {
  forma: string[];
  n?: number;
  chica?: boolean;
}) {
  return (
    <span className={`inline-flex ${chica ? "gap-0.5" : "gap-1"}`}>
      {forma.slice(-n).map((x, i) => (
        <span
          key={i}
          title={x === "g" ? "Victoria" : x === "p" ? "Derrota" : "Empate"}
          aria-label={x === "g" ? "Victoria" : x === "p" ? "Derrota" : "Empate"}
          className={`bg-card2 border border-line2 rounded w-[20px] h-[22px] inline-flex items-center justify-center text-[10px] font-bold ${x === "g" ? "text-ok" : x === "p" ? "text-bad" : "text-mut"}`}
        >
          {x.toUpperCase()}
        </span>
      ))}
    </span>
  );
}
export function TablaPosiciones({
  liga,
  filas,
  compacta,
  resaltar = [],
}: {
  liga: string;
  filas: FilaTabla[];
  compacta?: boolean;
  resaltar?: string[];
}) {
  if (!filas.length)
    return (
      <p role="status" className="text-sm text-mut py-6">
        No hay partidos suficientes para construir la clasificación.
      </p>
    );
  return (
    <>
      <div className={compacta ? "" : "sm:hidden"}>
        {filas.map((f, i) =>
          compacta ? (
            <div
              key={f.equipo}
              className="flex items-center gap-3 py-3 border-b border-line2 last:border-0"
            >
              <span className="w-4 text-xs text-mut">{i + 1}</span>
              <Crest liga={liga} equipo={f.equipo} size={28} />
              <span className="min-w-0 flex-1 text-sm font-semibold truncate">
                {f.equipo}
              </span>
              <span className="text-xs text-mut">{f.J} J</span>
              <span className="text-sm font-bold w-8 text-right">{f.PTS}</span>
            </div>
          ) : (
            <details
              key={f.equipo}
              className={`border-b border-line2 ${resaltar.includes(f.equipo) ? "bg-card2 rounded-lg" : ""}`}
            >
              <summary className="flex items-center gap-3 py-3 min-h-14 list-none">
                <span className="w-4 text-xs text-mut">{i + 1}</span>
                <Crest liga={liga} equipo={f.equipo} size={28} />
                <span className="min-w-0 flex-1 text-sm font-semibold truncate">
                  {f.equipo}
                </span>
                <span className="text-xs text-mut">{f.J} J</span>
                <b className="w-8 text-right">{f.PTS}</b>
                <span aria-hidden="true" className="text-mut text-xs">
                  ⌄
                </span>
              </summary>
              <div className="pb-4 pl-7 text-xs text-mut space-y-3">
                <p>
                  {f.G} victorias · {f.E} empates · {f.P} derrotas
                </p>
                <p>
                  Goles {f.GF} a favor / {f.GC} en contra · DG {f.DG}
                </p>
                <div>
                  <span className="mr-2">Forma</span>
                  <Forma forma={f.forma} />
                </div>
              </div>
            </details>
          ),
        )}
      </div>
      {!compacta && (
        <table className="st hidden sm:table">
          <caption className="sr-only">
            Clasificación calculada con los partidos cargados
          </caption>
          <thead>
            <tr>
              {[
                "Equipo",
                "J",
                "G",
                "E",
                "P",
                "GF",
                "GC",
                "DG",
                "Pts",
                "Forma",
              ].map((t) => (
                <th key={t} scope="col">
                  {t}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filas.map((f, i) => (
              <tr
                key={f.equipo}
                className={resaltar.includes(f.equipo) ? "bg-card2" : ""}
              >
                <th scope="row">
                  <span className="inline-flex items-center gap-2 text-txt font-semibold normal-case tracking-normal">
                    <span className="w-5 text-mut text-xs">{i + 1}</span>
                    <Crest liga={liga} equipo={f.equipo} size={28} />
                    {f.equipo}
                  </span>
                </th>
                {[f.J, f.G, f.E, f.P, f.GF, f.GC, f.DG, f.PTS].map((v, j) => (
                  <td key={j} className={j === 7 ? "font-bold" : ""}>
                    {v}
                  </td>
                ))}
                <td>
                  <Forma forma={f.forma} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <Nota>
        J = jugados · DG = diferencia de goles · Pts = puntos. Forma: G
        victoria, E empate, P derrota; antiguo → reciente. Calculada con los
        partidos disponibles, sin certificar clasificación oficial ni plazas de
        competiciones.
      </Nota>
    </>
  );
}

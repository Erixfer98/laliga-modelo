"use client";
import type { Grafico, Hist } from "@/lib/api";
import { pct } from "@/lib/fmt";
import { Nota } from "./ui";
export function BarrasPartidos({
  h,
  col,
  linea,
  mediaLiga,
  ok,
  color,
  sinLinea,
}: {
  h: Hist[];
  col: "a_favor" | "en_contra" | "total";
  linea: number;
  mediaLiga: number;
  ok: boolean[];
  color: string;
  sinLinea?: boolean;
}) {
  if (!h.length)
    return <p className="text-sm text-mut">Sin partidos con ese filtro.</p>;
  const filas = h.map((g, i) => ({ g, ok: ok[i] })).reverse();
  const mx = Math.max(...h.map((g) => g[col]), linea, mediaLiga, 1) * 1.15;
  return (
    <div
      role="img"
      aria-label={`Historial: ${filas.map((f) => `${f.g.rival}: ${f.g[col]}, ${f.ok ? "cumple" : "no cumple"}`).join("; ")}. Media liga ${mediaLiga}.`}
      className="scrollx pt-6 pb-7"
    >
      <div
        className="relative h-[120px]"
        style={{ minWidth: filas.length * 20 }}
      >
        <div className="flex items-end gap-1 h-full">
          {filas.map(({ g, ok }, i) => (
            <div
              key={i}
              className="flex-1 rounded-t relative"
              style={{
                height: `${Math.max((g[col] / mx) * 100, 2)}%`,
                background: ok ? color : "var(--miss)",
              }}
            >
              <span className="absolute -top-5 inset-x-0 text-center text-[10px]">
                {g[col]}
              </span>
              <span className="absolute -bottom-5 inset-x-0 text-center text-[10px] text-mut">
                {g.condicion === "Casa" ? "C" : "F"}
              </span>
            </div>
          ))}
        </div>
        {!sinLinea && (
          <div
            className="absolute inset-x-0 border-t border-dashed border-mark"
            style={{ bottom: `${(linea / mx) * 100}%` }}
          >
            <span className="absolute right-0 -top-4 text-[11px] bg-card rounded px-1">
              Línea {linea.toFixed(1)}
            </span>
          </div>
        )}
        <div
          className="absolute inset-x-0 border-t border-dotted border-warn"
          style={{ bottom: `${(mediaLiga / mx) * 100}%` }}
        >
          <span className="absolute left-0 -top-4 text-[11px] text-warn bg-card rounded px-1">
            Liga {mediaLiga.toFixed(1)}
          </span>
        </div>
      </div>
    </div>
  );
}
export function Matriz({
  g,
  local,
  visitante,
}: {
  g: Extract<Grafico, { tipo: "matriz" }>;
  local: string;
  visitante: string;
}) {
  return (
    <>
      <table className="w-full table-fixed border-separate border-spacing-1 text-[10px] sm:text-xs">
        <caption className="text-left text-sm font-semibold mb-4">
          Probabilidad por marcador · filas {local}, columnas {visitante}
        </caption>
        <thead>
          <tr>
            <th scope="col" className="text-mut">
              L / V
            </th>
            {Array.from({ length: g.k }, (_, y) => (
              <th scope="col" key={y} className="text-mut py-1">
                {y}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {g.celdas.map((fila, x) => (
            <tr key={x}>
              <th scope="row" className="text-mut">
                {x}
              </th>
              {fila.map((c, y) => (
                <td
                  key={y}
                  className="text-center py-2 rounded"
                  title={`${x}–${y}: ${pct(c.p, 2)} · ${c.push ? "devolución" : c.gana ? "acierto" : "fallo"}`}
                  style={{
                    background: c.gana
                      ? `hsl(214 80% ${94 - (10 * c.p) / g.max}%)`
                      : "var(--card2)",
                    color: c.gana ? "#1e3a8a" : "var(--txt)",
                  }}
                >
                  {pct(c.p, 1)}
                  <span className="block">
                    {c.push ? "↩" : c.gana ? "✓" : "·"}
                  </span>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <Nota>
        ✓ acierto · ↩ devolución · · fallo. Cada celda expresa la probabilidad
        de ese marcador. Masa visible {pct(g.masa_visible, 1)}, sin
        renormalizar.
      </Nota>
    </>
  );
}
export function BarrasPoisson({
  valores,
  signo,
  nota,
}: {
  valores: { x: number; p: number; gana: boolean }[];
  signo?: boolean;
  nota: string;
}) {
  if (!valores.length)
    return <p className="text-sm text-mut">Distribución no disponible.</p>;
  const mx = Math.max(...valores.map((v) => v.p), 1e-12);
  return (
    <>
      <div
        role="img"
        aria-label={`Distribución: ${valores.map((v) => `${v.x}: ${pct(v.p, 1)}, ${v.gana ? "acierto" : "no acierto"}`).join("; ")}`}
        className="scrollx pt-6 pb-7"
      >
        <div
          className="flex items-end gap-1 h-[120px]"
          style={{ minWidth: valores.length * 30 }}
        >
          {valores.map((v) => (
            <div
              key={v.x}
              className="flex-1 rounded-t relative"
              style={{
                height: `${Math.max((v.p / mx) * 100, 2)}%`,
                background: v.gana ? "var(--acc)" : "var(--miss)",
              }}
            >
              <span className="absolute -top-5 inset-x-0 text-center text-[10px]">
                {pct(v.p)}
              </span>
              <span className="absolute -bottom-5 inset-x-0 text-center text-[10px] text-mut">
                {signo && v.x > 0 ? `+${v.x}` : v.x}
                {v.gana ? " ✓" : ""}
              </span>
            </div>
          ))}
        </div>
      </div>
      <Nota>{nota.replaceAll("Verde =", "Azul ✓ =")}</Nota>
      <details className="mt-3">
        <summary className="min-h-11 flex items-center text-xs text-mut">
          Ver probabilidades del gráfico
        </summary>
        <table className="st">
          <caption className="sr-only">Probabilidad por cantidad</caption>
          <thead>
            <tr>
              <th scope="col">Cantidad</th>
              <th scope="col">Probabilidad</th>
              <th scope="col">Acierto</th>
            </tr>
          </thead>
          <tbody>
            {valores.map((v) => (
              <tr key={v.x}>
                <th scope="row">{v.x}</th>
                <td>{pct(v.p, 2)}</td>
                <td>{v.gana ? "Sí" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </>
  );
}

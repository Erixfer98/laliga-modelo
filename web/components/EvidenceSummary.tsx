"use client";
import { METRICAS, type Mercado, type VistaPartido } from "@/lib/api";
import { num, pct } from "@/lib/fmt";

export function EvidenceSummary({ v, p, n, filtro }: {
  v: Pick<VistaPartido, "local" | "visitante" | "metrica" | "var" | "medias_liga">;
  p: Mercado;
  n: number;
  filtro: string;
}) {
  return (
    <section id="evidencia" className="rounded-card border border-line2 bg-card p-4 sm:p-6 mt-5" aria-label="Evidencia histórica">
      <div className="eyebrow mb-1">04 · Contrastar la evidencia</div>
      <h2 className="text-xl font-extrabold mb-2">¿Qué muestra el historial?</h2>
      <p className="text-sm text-mut mb-4">
        {p.mercado} · últimos {n} partidos por equipo · {filtro === "Todos" ? "todas las condiciones" : "local en casa y visitante fuera"}.
      </p>
      <div className="grid sm:grid-cols-2 gap-3">
        {[{ equipo: v.local, hits: p.hl, total: p.nl, estado: v.var.local.estado, lado: "Local" },
          { equipo: v.visitante, hits: p.hv, total: p.nv, estado: v.var.visitante.estado, lado: "Visitante" }].map((item) => (
          <div className="rounded-xl bg-card2 p-4" key={item.equipo}>
            <p className="text-xs font-bold text-mut">{item.lado} · {item.equipo}</p>
            <div className="flex items-end justify-between gap-2 mt-2">
              <span className="num text-2xl">{item.hits}/{item.total}</span>
              <span className="text-xs text-mut">{item.total ? pct(item.hits / item.total, 1) : "Sin muestra"}</span>
            </div>
            <p className="text-xs text-mut mt-2">Cumplimientos históricos · {item.estado}</p>
          </div>
        ))}
      </div>
      <p className="text-xs text-mut mt-3">
        Media total de liga en {METRICAS[v.metrica]?.toLowerCase() || v.metrica}: {num(v.medias_liga.total, 2)}.
        El cumplimiento observado no es una probabilidad futura ni explica por sí solo los parámetros del modelo.
      </p>
    </section>
  );
}

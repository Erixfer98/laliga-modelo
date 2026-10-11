"use client";
import { METRICAS, type VistaPartido } from "@/lib/api";
import { num } from "@/lib/fmt";

export function LambdaSummary({ v }: { v: Pick<VistaPartido,
  "metrica" | "local" | "visitante" | "lambda_local" | "lambda_visitante" |
  "rango" | "medias_liga" | "var"> }) {
  const unidad = (METRICAS[v.metrica] || v.metrica).toLowerCase();
  const total = v.lambda_local + v.lambda_visitante;
  const diferencia = Math.abs(v.lambda_local - v.lambda_visitante);
  const lectura = diferencia < 0.01
    ? "El modelo estima una producción similar de " + unidad + " para ambos equipos."
    : "El modelo espera " + num(diferencia, 2) + " " + unidad +
      " más de " + (v.lambda_local > v.lambda_visitante ? v.local : v.visitante) +
      " que de su rival.";
  const items = [
    { id: "lambda-local", label: "Local", equipo: v.local, lambda: v.lambda_local, rango: v.rango.local },
    { id: "lambda-visitante", label: "Visitante", equipo: v.visitante, lambda: v.lambda_visitante, rango: v.rango.visitante },
    { id: "lambda-total", label: "Total esperado", equipo: "Ambos equipos", lambda: total, rango: v.rango.total },
  ];
  return (
    <section id="expectativa" data-testid="lambda-summary" aria-labelledby="lambda-title"
      className="rounded-card bg-card border border-line2 px-4 py-5 sm:p-6 mb-5">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <div className="eyebrow mb-1">01 · Punto de partida</div>
          <h2 id="lambda-title" className="text-xl sm:text-2xl font-extrabold tracking-tight">Qué espera el modelo</h2>
        </div>
        <span className="tag">λ · {METRICAS[v.metrica] || v.metrica}</span>
      </div>
      <div className="grid grid-cols-3 gap-2 sm:gap-4" aria-label="Parámetros lambda">
        {items.map((item) => (
          <div key={item.id} className="min-w-0 rounded-xl bg-card2 p-3 sm:p-4">
            <p className="text-[.67rem] sm:text-xs font-semibold text-mut">{item.label}</p>
            <div className="num text-2xl sm:text-4xl mt-2 text-acc" data-testid={item.id}>{num(item.lambda, 2)}</div>
            <p className="text-[.65rem] sm:text-xs text-mut mt-2 break-words">{item.equipo}</p>
            <p className="text-[.65rem] sm:text-xs text-mut2 mt-1">Rango: {num(item.rango[0], 2)}–{num(item.rango[1], 2)}</p>
          </div>
        ))}
      </div>
      <p className="text-sm leading-relaxed mt-4" data-testid="lambda-lectura">{lectura}</p>
      <div className="flex flex-wrap gap-x-5 gap-y-1 mt-3 text-xs text-mut">
        <span>Media de liga, total: {num(v.medias_liga.total, 2)}</span>
        <span>Variabilidad local: {v.var.local.estado}</span>
        <span>Variabilidad visitante: {v.var.visitante.estado}</span>
      </div>
      <p className="text-xs text-mut2 mt-3">λ es la cantidad esperada de {unidad} según el modelo; no es un resultado garantizado. Los rangos son escenarios heurísticos, sin cobertura estadística validada.</p>
    </section>
  );
}

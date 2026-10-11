"use client";
import { useState } from "react";
import type { Mercado } from "@/lib/api";

type Props = {
  grupo: string;
  mercados: Mercado[];
  elegido: string;
  onSelect: (market: string) => void;
  onExtend: (linea: number, over: boolean) => void;
  loading?: boolean;
};

/** Las líneas se obtienen del motor; nunca calculamos probabilidades en el cliente. */
export function LineSelector({ grupo, mercados, elegido, onSelect, onExtend, loading = false }: Props) {
  const [expanded, setExpanded] = useState(false);
  const opciones = mercados.filter((m) => m.grupo === grupo);
  const ou = opciones.filter((m) => m.seleccion?.regla?.tipo === "ou");
  const actual = opciones.find((m) => m.mercado === elegido) || opciones[0];
  if (!opciones.length) return null;
  if (!ou.length) {
    return (
      <div role="group" aria-label="Opciones del mercado" className="mb-4">
        <p className="text-xs font-semibold text-mut mb-2">Elegí un escenario</p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {opciones.map((m) => (
            <button type="button" key={m.mercado} onClick={() => onSelect(m.mercado)}
              aria-pressed={m.mercado === actual?.mercado}
              className={"min-h-11 rounded-lg border px-3 py-2 text-xs sm:text-sm font-semibold text-left " +
                (m.mercado === actual?.mercado ? "border-acc bg-card2 text-txt" : "border-line2 text-mut hover:bg-card2")}>
              {m.mercado}
            </button>
          ))}
        </div>
      </div>
    );
  }
  const lineas = [...new Set(ou.map((m) => m.linea))].sort((a, b) => a - b);
  const over = actual?.over ?? true;
  const selectedLine = actual?.linea;
  const min = lineas[0], max = lineas[lineas.length - 1];
  const adicionales = [min - 1, max + 1].filter((l) => l >= 0 && l <= 100);

  const seleccionar = (linea: number, dir: boolean) => {
    const m = ou.find((m) => m.linea === linea && m.over === dir);
    if (m) onSelect(m.mercado);
    else onExtend(linea, dir);
  };
  return (
    <div className="mb-4 rounded-xl bg-card2 p-3 sm:p-4" aria-busy={loading}>
      <div className="flex justify-between gap-2 items-center mb-3">
        <p className="text-xs font-bold">Elegí la línea</p>
        {loading && <span className="text-xs text-mut" role="status">Actualizando…</span>}
      </div>
      <div role="group" aria-label="Líneas disponibles" className="grid grid-cols-3 sm:grid-cols-5 gap-2">
        {lineas.map((l) => (
          <button key={l} type="button" aria-label={"Línea " + l.toFixed(1)}
            aria-pressed={l === selectedLine} onClick={() => seleccionar(l, over)}
            className={"min-h-12 rounded-lg border text-sm font-bold transition-colors " +
              (l === selectedLine ? "primary border-acc" : "bg-card border-line hover:border-acc")}>
            {l.toFixed(1)}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 mt-4">
        <div role="group" aria-label="Dirección del mercado" className="inline-flex rounded-lg border border-line bg-card p-1">
          {([{ value: true, label: "Más de" }, { value: false, label: "Menos de" }]).map((x) => (
            <button type="button" key={x.label} onClick={() => seleccionar(selectedLine, x.value)}
              aria-pressed={over === x.value}
              className={"min-h-11 px-4 text-sm font-semibold rounded-md " +
                (over === x.value ? "primary" : "text-mut hover:bg-card2")}>
              {x.label}
            </button>
          ))}
        </div>
        {adicionales.length > 0 && (
          <button type="button" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}
            className="min-h-11 text-sm font-semibold text-acc px-2">
            {expanded ? "Ocultar líneas adicionales" : "Ver más líneas"}
          </button>
        )}
      </div>
      {expanded && adicionales.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-3 border-t border-line pt-3"
          role="group" aria-label="Consultar líneas adicionales">
          {adicionales.map((l) => (
            <button type="button" key={l} onClick={() => onExtend(l, over)}
              className="rounded-lg border border-line bg-card min-h-11 px-3 text-sm font-semibold">
              Consultar {l.toFixed(1)}
            </button>
          ))}
        </div>
      )}
      <p className="text-xs text-mut mt-3">Cada cambio muestra la probabilidad calculada para esa línea. Si consultás una línea adicional, el motor recalculará la ventana disponible.</p>
    </div>
  );
}

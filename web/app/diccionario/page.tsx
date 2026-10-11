"use client";
import { useEffect, useState } from "react";
import type { Diccionario as Dic } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { Card, Cargando, ErrorBox, Nota } from "@/components/ui";
export default function Diccionario() {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  useEffect(() => {
    const id = setTimeout(() => setQuery(q), 250);
    return () => clearTimeout(id);
  }, [q]);
  const {
    data: grupos,
    error,
    reintentar,
  } = useApi<Dic>("/diccionario", { q: query });
  return (
    <>
      <div className="mb-6">
        <div className="eyebrow mb-2">Entender antes de interpretar</div>
        <h1 className="page-title">Cómo funciona Kuota.</h1>
        <p className="text-sm text-mut mt-2">
          Probabilidades, mercados y sus límites, en palabras claras.
        </p>
      </div>
      <div className="grid md:grid-cols-3 gap-4 mb-6">
        {[
          {
            t: "Probabilidad ≠ certeza",
            d: "El porcentaje es una estimación del modelo con datos históricos. Un suceso poco probable puede ocurrir.",
          },
          {
            t: "Probabilidad ≠ rentabilidad",
            d: "El valor esperado depende también de la cuota y de las reglas de devolución. Kuota no proporciona cuotas de casas.",
          },
          {
            t: "Sensibilidad ≠ confianza",
            d: "Los rangos de la app son escenarios heurísticos. No son intervalos de confianza con cobertura validada.",
          },
        ].map((x) => (
          <Card key={x.t} titulo={x.t}>
            <p className="text-sm leading-relaxed text-mut">{x.d}</p>
          </Card>
        ))}
      </div>
      <label className="block max-w-xl mb-6 text-sm font-semibold">
        Buscar en el glosario
        <input
          className="ctl mt-2"
          type="search"
          placeholder="Por ejemplo: devolución, Kelly…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </label>
      {error ? (
        <ErrorBox error={error} reintentar={reintentar} />
      ) : !grupos ? (
        <Cargando alto={260} />
      ) : grupos.length ? (
        <div className="grid lg:grid-cols-2 gap-4 items-start">
          {grupos.map((g) => (
            <Card key={g.grupo} titulo={g.grupo}>
              <p className="text-xs text-mut mb-4">{g.descripcion}</p>
              {g.items.map((it) => (
                <details key={it.termino} className="border-t border-line2">
                  <summary className="font-semibold text-sm min-h-12 py-3">
                    {it.termino}
                  </summary>
                  <p className="text-sm leading-relaxed text-mut pb-4">
                    {it.definicion}
                  </p>
                </details>
              ))}
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <p role="status" className="text-sm text-mut">
            No hay términos con “{query}”. Prueba otra palabra.
          </p>
        </Card>
      )}
      <Nota>
        El modelo no incorpora lesiones, alineaciones ni árbitro. Las
        probabilidades no sustituyen la evaluación de la calidad y vigencia de
        los datos.
      </Nota>
    </>
  );
}

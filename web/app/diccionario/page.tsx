"use client";
// Glosario: qué significa cada término de la app, en palabras simples.
import { useState } from "react";
import type { Diccionario as Dic } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { Card, Cargando, ErrorBox } from "@/components/ui";

export default function Diccionario() {
  const [q, setQ] = useState("");
  const { data: grupos, error } = useApi<Dic>("/diccionario", { q });
  if (error) return <ErrorBox error={error} />;
  return (
    <>
      <div className="px-1 mt-3 mb-2">
        <div className="text-[1.4rem] font-extrabold tracking-tight">Glosario</div>
        <div className="text-[0.82rem] text-mut">Qué significa cada término que ves en la app, en palabras simples.</div>
      </div>
      <input className="ctl" placeholder="Buscar un término…" value={q} onChange={(e) => setQ(e.target.value)} />
      {!grupos ? <Cargando alto={300} /> : grupos.map((g) => (
        <Card key={g.grupo} titulo={g.grupo} desc={g.descripcion}>
          {g.items.map((it) => (
            <div key={it.termino} className="py-2.5 border-t border-line2 first:border-t-0">
              <div className="font-extrabold text-[0.95rem]">{it.termino}</div>
              <div className="text-[0.86rem] leading-[1.55] mt-0.5 text-mut">{it.definicion}</div>
            </div>
          ))}
        </Card>
      ))}
      {grupos && !grupos.length && <Card><div className="text-[0.84rem] text-mut">Nada con &ldquo;{q}&rdquo;.</div></Card>}
    </>
  );
}

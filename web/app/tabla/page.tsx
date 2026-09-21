"use client";
// Tabla de posiciones por temporada.
import { useState } from "react";
import type { VistaTabla } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { useStore } from "@/lib/store";
import { Card, Cargando, ErrorBox } from "@/components/ui";
import { LigaLogo } from "@/components/Crest";
import { TablaPosiciones } from "@/components/Tabla";

export default function Tabla() {
  const { liga } = useStore();
  const [temp, setTemp] = useState<{ liga: string; temporada: string } | null>(null);
  const temporada = temp?.liga === liga ? temp.temporada : undefined;
  const { data: v, error } = useApi<VistaTabla>(`/liga/${liga}/tabla`, { temporada });

  if (error) return <ErrorBox error={error} />;
  if (!v) return <Cargando alto={420} />;
  return (
    <Card className="px-3!"
      titulo={<span className="inline-flex items-center gap-2"><LigaLogo liga={liga} size={22} /> {v.nombre}</span>}
      desc="Calculada con los partidos cargados en la base. Las zonas de Champions, Europa y descenso son orientativas (4 / 2 / 3)."
      right={
        <select className="ctl w-auto! min-h-[36px]! py-1! text-[0.82rem]" value={v.temporada} onChange={(e) => setTemp({ liga, temporada: e.target.value })}>
          {v.temporadas.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      }>
      <TablaPosiciones liga={liga} filas={v.tabla} />
    </Card>
  );
}

"use client";
import { useState } from "react";
import type { VistaTabla } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { useStore } from "@/lib/store";
import { Card, Cargando, ErrorBox } from "@/components/ui";
import { LigaLogo } from "@/components/Crest";
import { TablaPosiciones } from "@/components/Tabla";
export default function Tabla() {
  const { liga } = useStore();
  const [temp, setTemp] = useState<{ liga: string; temporada: string } | null>(
    null,
  );
  const {
    data: v,
    error,
    reintentar,
  } = useApi<VistaTabla>(`/liga/${liga}/tabla`, {
    temporada: temp?.liga === liga ? temp.temporada : undefined,
  });
  return (
    <>
      <div className="mb-6">
        <div className="eyebrow mb-2">La temporada, en contexto</div>
        <h1 className="page-title">Tabla de posiciones.</h1>
        <p className="text-sm text-mut mt-2">
          Clasificación calculada con los partidos registrados.
        </p>
      </div>
      {error ? (
        <ErrorBox error={error} reintentar={reintentar} />
      ) : !v ? (
        <Cargando alto={420} />
      ) : (
        <Card
          titulo={
            <span className="flex items-center gap-2">
              <LigaLogo liga={liga} size={24} />
              {v.nombre}
            </span>
          }
          right={
            <label>
              <span className="sr-only">Temporada</span>
              <select
                aria-label="Temporada"
                className="ctl w-auto!"
                value={v.temporada}
                onChange={(e) => setTemp({ liga, temporada: e.target.value })}
              >
                {v.temporadas.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
          }
        >
          <TablaPosiciones liga={liga} filas={v.tabla} />
        </Card>
      )}
    </>
  );
}

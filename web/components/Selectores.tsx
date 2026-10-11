"use client";
import { useEffect, useState } from "react";
import { api, LIGAS, type VistaInicio } from "@/lib/api";
import { useStore } from "@/lib/store";
import { Crest, LigaLogo } from "./Crest";
const cache: Record<string, { equipos: string[]; time: number }> = {};
const pending: Record<string, Promise<string[]> | undefined> = {};
export function useEquipos(liga: string) {
  const [rev, setRev] = useState(0);
  const [result, setResult] = useState<{
    liga: string;
    equipos: string[];
    error: string | null;
  }>({ liga: "", equipos: [], error: null });
  useEffect(() => {
    let live = true;
    if (cache[liga] && Date.now() - cache[liga].time < 300000) {
      setResult({ liga, equipos: cache[liga].equipos, error: null });
      return;
    }
    pending[liga] ??= api<VistaInicio>(`/liga/${liga}`)
      .then((v) => {
        cache[liga] = { equipos: v.equipos, time: Date.now() };
        return v.equipos;
      })
      .finally(() => {
        delete pending[liga];
      });
    pending[liga]!.then((equipos) => {
      if (live) setResult({ liga, equipos, error: null });
    }).catch((e: Error) => {
      if (live) setResult({ liga, equipos: [], error: e.message });
    });
    return () => {
      live = false;
    };
  }, [liga, rev]);
  return {
    equipos: result.liga === liga ? result.equipos : [],
    error: result.liga === liga ? result.error : null,
    reintentar: () => {
      delete cache[liga];
      setRev((v) => v + 1);
    },
  };
}
export function usePartido() {
  const { liga, partidos, setPartido } = useStore();
  const { equipos, error, reintentar } = useEquipos(liga);
  const saved = partidos[liga];
  const local =
    saved?.local && equipos.includes(saved.local)
      ? saved.local
      : equipos.includes("Real Madrid")
        ? "Real Madrid"
        : (equipos[0] ?? "");
  const others = equipos.filter((e) => e !== local);
  const visitante =
    saved?.visitante && others.includes(saved.visitante)
      ? saved.visitante
      : (others[0] ?? "");
  return {
    equipos,
    local,
    visitante,
    listo: equipos.length > 1,
    error,
    reintentar,
    setLocal: (l: string) =>
      setPartido(liga, {
        local: l,
        visitante:
          l === visitante ? (equipos.find((e) => e !== l) ?? "") : visitante,
      }),
    setVisitante: (v: string) => setPartido(liga, { local, visitante: v }),
  };
}
export function CabeceraPartido({ sub }: { sub?: React.ReactNode }) {
  const { liga } = useStore();
  const {
    equipos,
    local,
    visitante,
    setLocal,
    setVisitante,
    error,
    reintentar,
  } = usePartido();
  return (
    <section
      className="match-stripe rounded-card bg-card border border-line2 p-4 md:p-6 mb-5"
      aria-label="Elegir enfrentamiento"
    >
      <div className="flex items-center gap-2 text-xs text-mut mb-5">
        <LigaLogo liga={liga} size={20} />
        <span className="font-semibold">{LIGAS[liga]}</span>
        <span className="ml-auto text-[.7rem]">Selección manual</span>
      </div>
      <div className="grid grid-cols-[1fr_28px_1fr] items-start gap-2 md:gap-8">
        {[
          {
            nombre: local,
            label: "Local",
            opciones: equipos,
            change: setLocal,
            lado: "l" as const,
          },
          {
            nombre: visitante,
            label: "Visitante",
            opciones: equipos.filter((e) => e !== local),
            change: setVisitante,
            lado: "v" as const,
          },
        ].map((team, i) => (
          <div
            key={team.label}
            className={i ? "col-start-3 row-start-1 min-w-0" : "min-w-0"}
          >
            <div className="flex flex-col md:flex-row items-center md:items-start gap-3">
              <Crest
                liga={liga}
                equipo={team.nombre}
                size={64}
                lado={team.lado}
              />
              <div className="min-w-0 text-center md:text-left">
                <div className="eyebrow mb-1">{team.label}</div>
                <div className="text-sm md:text-xl font-extrabold tracking-tight leading-snug min-h-10 md:min-h-7">
                  {team.nombre || "Elige un equipo"}
                </div>
              </div>
            </div>
            <label className="block mt-3">
              <span className="sr-only">Equipo {team.label.toLowerCase()}</span>
              <select
                disabled={!equipos.length}
                className="ctl text-sm!"
                value={team.nombre}
                onChange={(e) => team.change(e.target.value)}
                aria-label={`Equipo ${team.label.toLowerCase()}`}
              >
                <option value="" disabled>
                  Elige un equipo
                </option>
                {team.opciones.map((e) => (
                  <option key={e} value={e}>
                    {e}
                  </option>
                ))}
              </select>
            </label>
          </div>
        ))}
        <div className="col-start-2 row-start-1 text-mut text-xs font-bold pt-6 text-center">
          VS
        </div>
      </div>
      {sub && <div className="text-xs text-mut mt-4">{sub}</div>}
      {error && (
        <div role="alert" className="text-sm text-bad mt-3">
          No pudimos cargar los equipos.{" "}
          <button onClick={reintentar} className="underline min-h-11">
            Reintentar equipos
          </button>
        </div>
      )}
    </section>
  );
}

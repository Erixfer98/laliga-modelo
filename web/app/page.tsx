"use client";
// Partido: la pantalla principal. Arriba los equipos y la métrica; después λ, la tabla de mercados
// (probabilidad, cuota justa y en cuántos de los últimos N partidos se cumplió) y el cara a cara.
import { useEffect, useRef, useState } from "react";
import { METRICAS, METRICA_CORTA, type Cfg, type VistaCara } from "@/lib/api";
import { useStore } from "@/lib/store";
import { useApi } from "@/lib/useApi";
import { usePartidoRapido, type Compacto, type Filtro, type MercadoCorto } from "@/lib/partido";
import { identidadSeleccion } from "@/lib/selecciones";
import { usePartido } from "@/components/Selectores";
import { CaraACara, Equipos, HojaMercado, Lambdas, TablaMercados } from "@/components/Partido";
import { ErrorBox } from "@/components/ui";

const NS = [5, 10];

export default function Partido() {
  const { liga, met, setMet, boleto, addLeg } = useStore();
  const { equipos, local, visitante, setLocal, setVisitante, listo, error: errorEquipos, reintentar: reintentarEquipos } = usePartido();
  const [n, setN] = useState(5);
  const [filtro, setFiltro] = useState<Filtro>("Todos");
  const partido = `${liga}|${local}|${visitante}`;
  const [lineas, setLineas] = useState<{ partido: string; cfgs: Record<string, Cfg> }>({ partido: "", cfgs: {} });
  const cfgs = lineas.partido === partido ? lineas.cfgs : {};
  const base = listo && local && visitante ? { liga, local, visitante, n, filtro } : null;
  const { data, error, reintentar } = usePartidoRapido(base, met, cfgs);
  const cara = useApi<VistaCara>(base ? `/liga/${liga}/cara` : null, { local, visitante }, { cache: true });
  const caraOk = cara.data && cara.data.liga === liga && cara.data.local === local && cara.data.visitante === visitante ? cara.data : null;

  // Mientras llega la métrica pedida, se deja la tabla anterior del mismo partido y métrica (atenuada).
  const ultimo = useRef<Compacto | null>(null);
  if (data) ultimo.current = data;
  const previo = ultimo.current;
  const d =
    data ??
    (previo && previo.liga === liga && previo.local === local && previo.visitante === visitante && previo.metrica === met ? previo : null);
  const actualizando = !data && !!d;

  const [abierto, setAbierto] = useState<MercadoCorto | null>(null);
  const enBoleto = new Set(
    d ? d.mercados.filter((m) => boleto.some((l) => identidadSeleccion(l.seleccion) === identidadSeleccion(m.seleccion))).map((m) => m.mercado) : [],
  );
  const masLineas = (grupo: string) => {
    if (!d) return;
    const actual = cfgs[met] ?? d.cfg;
    const [centro, rango] = actual[grupo];
    setLineas({ partido, cfgs: { ...cfgs, [met]: { ...actual, [grupo]: [centro, rango + 1] } } });
  };

  // Si el servidor estaba dormido tarda ~1 min: se avisa a los 5 s.
  const [lento, setLento] = useState(false);
  useEffect(() => {
    setLento(false);
    if (d) return;
    const t = setTimeout(() => setLento(true), 5000);
    return () => clearTimeout(t);
  }, [d, partido, met]);

  return (
    <div className="max-w-2xl mx-auto space-y-3">
      <h1 className="sr-only">Partido</h1>
      {errorEquipos ? (
        <ErrorBox error={errorEquipos} reintentar={reintentarEquipos} />
      ) : (
        <Equipos liga={liga} equipos={equipos} local={local} visitante={visitante} setLocal={setLocal} setVisitante={setVisitante} />
      )}

      <div role="group" aria-label="Métrica" className="scrollx flex lg:flex-wrap gap-1.5 -mx-4 px-4 lg:mx-0 lg:px-0 pb-1">
        {Object.keys(METRICAS).map((m) => (
          <button
            key={m}
            type="button"
            aria-pressed={m === met}
            onClick={() => setMet(m)}
            className={`shrink-0 min-h-10 px-3.5 rounded-full text-sm font-bold border ${m === met ? "primary border-transparent" : "bg-card border-line2 text-mut"}`}
          >
            {METRICA_CORTA[m]}
          </button>
        ))}
      </div>

      {error && !d ? (
        <ErrorBox error={error} reintentar={reintentar} />
      ) : !d ? (
        <div role="status" className="space-y-3">
          <div className="grid grid-cols-3 gap-2">
            {[0, 1, 2].map((i) => <div key={i} className="h-[88px] rounded-xl bg-card2 animate-pulse" />)}
          </div>
          <div className="h-72 rounded-card bg-card2 animate-pulse" />
          <p className="text-xs text-mut text-center">
            {lento ? "El servidor estaba dormido; tarda hasta 1 minuto en despertar…" : "Cargando el partido…"}
          </p>
        </div>
      ) : (
        <div className={actualizando ? "opacity-60 transition-opacity" : ""} aria-busy={actualizando}>
          <Lambdas d={d} />
          <div className="flex items-center gap-2 my-3">
            <Segmento
              label="Partidos recientes"
              opciones={NS.map((x) => ({ v: x, t: `Últ. ${x}` }))}
              valor={n}
              onChange={setN}
            />
            <span className="flex-1" />
            <Segmento
              label="Condición"
              opciones={[{ v: "Todos" as Filtro, t: "Todos" }, { v: "Como jugarán" as Filtro, t: "Casa / fuera" }]}
              valor={filtro}
              onChange={setFiltro}
            />
          </div>
          <p className="text-xs text-mut mb-3 leading-relaxed">
            λ = cuántos {METRICAS[met].toLowerCase()} espera el modelo. {n === 5 ? "4/5" : "8/10"} = en {n === 5 ? 4 : 8} de sus últimos {n} partidos se cumplió el mercado
            {filtro === "Todos" ? "" : ` (${local} solo en casa, ${visitante} solo fuera)`}. En los mercados de un equipo, la columna del rival cuenta lo que el rival recibió.
          </p>
          <TablaMercados d={d} enBoleto={enBoleto} abrir={setAbierto} masLineas={masLineas} />
        </div>
      )}

      {base && <CaraACara c={caraOk} met={met} />}

      {abierto && d && (
        <HojaMercado
          key={abierto.mercado + d.data_version}
          d={d}
          m={d.mercados.find((m) => m.mercado === abierto.mercado) ?? abierto}
          cfg={cfgs[met]}
          boleto={boleto}
          addLeg={addLeg}
          cerrar={() => setAbierto(null)}
        />
      )}
    </div>
  );
}

function Segmento<T extends string | number>({
  label,
  opciones,
  valor,
  onChange,
}: {
  label: string;
  opciones: { v: T; t: string }[];
  valor: T;
  onChange: (v: T) => void;
}) {
  return (
    <div role="group" aria-label={label} className="flex p-0.5 rounded-lg bg-card2">
      {opciones.map((o) => (
        <button
          key={String(o.v)}
          type="button"
          aria-pressed={o.v === valor}
          onClick={() => onChange(o.v)}
          className={`min-h-9 px-3 rounded-md text-xs font-bold ${o.v === valor ? "bg-card text-txt shadow-sm" : "text-mut"}`}
        >
          {o.t}
        </button>
      ))}
    </div>
  );
}

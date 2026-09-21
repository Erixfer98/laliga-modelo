"use client";
// Partido = Armar + Analizar en una sola pantalla: cabecera con escudos, mercados y el detalle de la pata elegida.
import { useState } from "react";
import { METRICAS, METRICA_CORTA, type Cfg, type VistaPartido } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { useStore } from "@/lib/store";
import { justa, num, pct, signed } from "@/lib/fmt";
import { Bar, Btn, Card, Cargando, ErrorBox, Kpi, Nota, Pills, Sec, T, Tag, Toggle, Trio } from "@/components/ui";
import { CabeceraPartido, usePartido } from "@/components/Selectores";
import { Crest } from "@/components/Crest";
import { Chip, GraficoModelo, HistorialEquipo, ListaPartidos } from "@/components/PataDetalle";

const NS = [3, 5, 8, 10, 15, 20, 30];

export default function Partido() {
  const { liga, met, setMet, addLeg } = useStore();
  const { local, visitante, listo } = usePartido();
  const clave = `${liga}|${local}|${visitante}|${met}`;   // cuando cambia el partido o la métrica, se reinician líneas, grupo y pata
  const [sel, setSel] = useState<{ clave: string; grupo?: string; pata?: string; cfg?: Cfg }>({ clave });
  const s = sel.clave === clave ? sel : { clave };
  const [n, setN] = useState(5);
  const [filtro, setFiltro] = useState<"Todos" | "Como jugarán">("Todos");
  const [solo, setSolo] = useState(false);
  const [cuota, setCuota] = useState("1.90");
  const [aviso, setAviso] = useState("");

  const { data: v, error, loading } = useApi<VistaPartido>(listo ? `/liga/${liga}/partido` : null,
    { local, visitante, met, n, filtro, grupo: s.grupo, pata: s.pata, cfg: s.cfg ? JSON.stringify(s.cfg) : undefined });

  const pillsMet = <Pills opciones={Object.keys(METRICAS)} valor={met} onChange={setMet} format={(m) => METRICA_CORTA[m]} />;
  if (error) return <><CabeceraPartido />{pillsMet}<ErrorBox error={error} /></>;
  if (!v || v.local !== local || v.visitante !== visitante || v.metrica !== met) {
    return <><CabeceraPartido />{pillsMet}<Cargando alto={170} /><Cargando alto={320} /></>;
  }

  const grupo = s.grupo && v.grupos.includes(s.grupo) ? s.grupo : v.grupos[0];
  const p = v.pata;
  const lista = v.mercados.filter((m) => m.grupo === grupo && (!solo || m.cls === "exc" || m.cls === "bue"));
  const conLineas = !["Resultado", "Mayor número"].includes(grupo);
  const [centro, rango] = v.cfg[grupo] ?? [0.5, 1];
  const cuotaN = Number(cuota) || 0;
  const ev = p.prob * cuotaN - 1, evLo = p.lo * cuotaN - 1;
  const nombreMet = METRICAS[met].toLowerCase();

  const cambiarGrupo = (g: string) => setSel({ clave, cfg: s.cfg, grupo: g, pata: undefined });          // la pata pasa a la primera del grupo
  const cambiarLineas = (c: number, r: number) => setSel({ clave, cfg: { ...v.cfg, [grupo]: [c, r] }, grupo, pata: undefined });
  const agregar = () => {
    if (cuotaN < 1.01) return;
    addLeg({ partido: v.partido, metrica: METRICAS[met], mercado: p.mercado, prob: p.prob, cuota: cuotaN, cal: p.tag, cls: p.cls, lo: p.lo, hi: p.hi });
    setAviso(`${p.mercado} agregada al boleto`); setTimeout(() => setAviso(""), 2500);
  };
  const filaModelo = (nombre: string, lado: "l" | "v" | null, lam: number, [lo, hi]: [number, number], ref: number, chip: React.ReactNode) => (
    <div className="flex items-center gap-2.5 py-2.5 border-t border-line2 first:border-t-0">
      {lado ? <Crest liga={liga} equipo={nombre} size={34} lado={lado} /> : <span className="w-[34px] h-[34px] rounded-full bg-card2 inline-flex items-center justify-center text-[0.7rem] font-extrabold text-mut2">Σ</span>}
      <div className="flex-1 min-w-0">
        <div className="font-extrabold text-[0.95rem] truncate">{nombre}</div>
        <div className="text-[0.74rem] text-mut2 flex flex-wrap gap-x-2">
          <span>rango <b className="text-mut">{num(lo)}–{num(hi)}</b></span><span>liga <b className="text-mut">{num(ref)}</b></span>
          <span className={`font-bold ${lam - ref >= 0 ? "text-ok" : "text-bad"}`}>{signed(lam - ref)}</span>{chip && <span>{chip}</span>}
        </div>
      </div>
      <div className="num text-[1.7rem]">{num(lam)}</div>
    </div>
  );

  return (
    <div className={loading ? "opacity-70 transition-opacity" : "transition-opacity"}>
      <CabeceraPartido sub={`temporada en curso`} />
      {pillsMet}

      <Card titulo={`Esperado por el modelo · ${nombreMet}`}
        desc={`Cuántos ${nombreMet} espera el modelo para este partido (λ, el número grande) y su rango de confianza del 80%. Cuanto más angosto el rango, más seguro el número. liga = media de la liga en esa condición · el verde/rojo es λ menos esa media · el punto es qué tan variable es el equipo frente a la liga (verde estable, ámbar normal, rojo volátil, gris pocos datos) y las veces que varía.`}>
        {filaModelo(v.local, "l", v.lambda_local, v.rango.local, v.medias_liga.local, <Chip {...v.var.local} />)}
        {filaModelo(v.visitante, "v", v.lambda_visitante, v.rango.visitante, v.medias_liga.visitante, <Chip {...v.var.visitante} />)}
        {filaModelo("Total del partido", null, v.lambda_local + v.lambda_visitante, v.rango.total, v.medias_liga.total, null)}
      </Card>

      <Card titulo="Mercados" desc={`Probabilidad de cada mercado según el modelo y en cuántos de los últimos ${n} partidos de cada equipo se habría cumplido. Calificación = 60% probabilidad Poisson + 40% cumplimiento. Barra = probabilidad; marca vertical = % histórico. ↕ = un equipo volátil baja un nivel la calificación. Toca un mercado para analizarlo abajo.`}
        className="px-3!">
        <Pills opciones={v.grupos} valor={grupo} onChange={cambiarGrupo} small />
        <div className="flex flex-wrap items-center gap-2 mt-1 mb-2">
          {conLineas && (
            <>
              <div className="flex items-center rounded-2xl bg-card2 overflow-hidden">
                <button type="button" className="px-3.5 min-h-[44px] text-mut hover:text-txt text-[1.1rem]" onClick={() => cambiarLineas(Math.max(centro - 1, 0.5), rango)}>−</button>
                <div className="px-1 min-w-[84px] text-center text-[0.84rem]"><span className="text-mut2 text-[0.68rem] font-bold uppercase">línea </span><b>{centro}</b></div>
                <button type="button" className="px-3.5 min-h-[44px] text-mut hover:text-txt text-[1.1rem]" onClick={() => cambiarLineas(Math.min(centro + 1, 60.5), rango)}>+</button>
              </div>
              <select className="ctl w-auto!" value={rango} onChange={(e) => cambiarLineas(centro, Number(e.target.value))}>
                {[0, 1, 2, 3, 4].map((r) => <option key={r} value={r}>± {r} líneas</option>)}
              </select>
            </>
          )}
          <select className="ctl w-auto!" value={n} onChange={(e) => setN(Number(e.target.value))}>
            {NS.map((x) => <option key={x} value={x}>últ. {x} partidos</option>)}
          </select>
          <Toggle label="Como jugarán" valor={filtro !== "Todos"} onChange={(x) => setFiltro(x ? "Como jugarán" : "Todos")} />
          <Toggle label="Solo Buena o mejor" valor={solo} onChange={setSolo} />
        </div>
        {lista.map((m) => {
          const activa = m.mercado === p.mercado;
          return (
            <button key={m.mercado} type="button" onClick={() => setSel({ clave, cfg: s.cfg, grupo, pata: m.mercado })}
              className={`block w-full text-left px-3 py-3 mb-1.5 rounded-2xl transition-colors ${activa ? "bg-card2 ring-2 ring-acc/70" : "bg-card2/40 hover:bg-card2"}`}>
              <div className="flex items-center gap-2">
                <div className="flex-1 min-w-0">
                  <div className="font-extrabold text-[0.98rem] leading-tight">{m.mercado}</div>
                  <div className="text-[0.76rem] text-mut mt-0.5">justa <span className="text-txt font-bold">{justa(m.prob)}</span> · {m.hl}/{m.nl} · {m.hv}/{m.nv}</div>
                </div>
                <div className="w-[72px] text-right shrink-0 pl-1">
                  <div className="num text-[1.6rem]">{pct(m.prob)}</div>
                  <div className="text-[0.7rem] text-mut2 whitespace-nowrap">{pct(m.lo)}–{pct(m.hi)}</div>
                </div>
                <div className="w-[84px] text-right shrink-0"><Tag cls={m.cls}>{m.tag}</Tag></div>
              </div>
              <Bar valor={m.prob} marca={m.tasa} max={1} color={m.prob >= 0.6 ? "var(--ok)" : "var(--warn)"} alto={5} />
            </button>
          );
        })}
        {!lista.length && <div className="text-[0.8rem] text-mut py-3 px-1">Ningún mercado con calificación Buena o mejor en este grupo. Quita el filtro o cambia de línea.</div>}
      </Card>

      {/* ---------------------------------------------------------------- detalle de la pata */}
      <Card hero="hero-ok" titulo={p.mercado} right={<Tag cls={p.cls}>{p.tag}</Tag>}
        desc={`Probabilidad de la pata según el modelo y en cuántos de los últimos ${n} partidos de los dos equipos se cumplió. Calificación = 60% probabilidad Poisson + 40% cumplimiento histórico; ↕ equipo volátil la baja un nivel. Los escenarios repiten el cálculo con la λ pesimista y la optimista de cada equipo.`}>
        <div className="text-[0.78rem] text-mut -mt-2 mb-1">{METRICAS[met]} · {v.partido}</div>
        <Trio items={[
          { valor: pct(p.prob), label: "Modelo", sub: `justa ${justa(p.prob)}` },
          { valor: pct(p.tasa), label: "Histórico", sub: `${p.hl + p.hv} de ${p.nl + p.nv} partidos` },
        ]} />
        <Bar valor={p.prob} marca={p.tasa} max={1} color="var(--acc)" />
        <div className="mt-3">
          <Kpi flat items={[
            { label: "Pesimista", valor: pct(p.lo), sub: `justa ${justa(p.lo)}` },
            { label: "Modelo", valor: pct(p.prob), sub: `justa ${justa(p.prob)}` },
            { label: "Optimista", valor: pct(p.hi), sub: `justa ${justa(p.hi)}` },
          ]} />
        </div>
      </Card>

      <Card titulo="Agregar al boleto" desc="Escribe la cuota que paga la casa y revisa el EV antes de agregar. EV = probabilidad × cuota − 1. El EV pesimista usa la probabilidad pesimista: si sigue positivo, la pata aguanta un modelo optimista.">
        <div className="flex items-end gap-2 mb-2.5">
          <label className="flex-1"><T>Cuota casa</T>
            <input className="ctl mt-1 text-[1.1rem] font-extrabold" type="number" inputMode="decimal" step="0.01" min="1.01" max="50" value={cuota} onChange={(e) => setCuota(e.target.value)} /></label>
          <Btn primary onClick={agregar}>Agregar</Btn>
        </div>
        <Kpi items={[
          { label: "EV modelo", valor: signed(ev), sub: `prob. ${pct(p.prob)} · justa ${justa(p.prob)}`, cls: ev > 0 ? "text-ok" : "text-bad" },
          { label: "EV pesimista", valor: signed(evLo), sub: `prob. ${pct(p.lo)}`, cls: evLo > 0 ? "text-ok" : "text-bad" },
        ]} />
        {aviso && <div className="text-[0.84rem] text-ok font-bold mt-2">✓ {aviso}</div>}
      </Card>

      <Sec titulo="Historial por equipo" desc={`Últimos ${n} partidos de cada uno${filtro !== "Todos" ? " (local en casa, visitante fuera)" : ""}. Línea punteada blanca = línea del mercado; naranja = media de la liga. Debajo, media, mediana y desviación (qué tanto varía de partido a partido).`} />
      <HistorialEquipo v={v} p={p} lado="l" />
      <HistorialEquipo v={v} p={p} lado="v" />

      <details open className="mt-3 group">
        <summary className="flex items-center justify-between px-1 py-1 text-[1.15rem] font-extrabold tracking-tight">Partido a partido <span className="text-mut2 text-[0.78rem] font-bold group-open:hidden">mostrar</span><span className="text-mut2 text-[0.78rem] font-bold hidden group-open:inline">ocultar</span></summary>
        <ListaPartidos v={v} p={p} lado="l" />
        <ListaPartidos v={v} p={p} lado="v" />
      </details>
      <details className="mt-2 group">
        <summary className="flex items-center justify-between px-1 py-1 text-[1.15rem] font-extrabold tracking-tight">Qué dice el modelo <span className="text-mut2 text-[0.78rem] font-bold group-open:hidden">mostrar</span><span className="text-mut2 text-[0.78rem] font-bold hidden group-open:inline">ocultar</span></summary>
        <Card><GraficoModelo v={v} p={p} /></Card>
      </details>
      <div className="h-2" />
      <Nota>{`Datos: football-data.co.uk y ESPN. El modelo no sabe de lesiones, alineaciones ni árbitro.`}</Nota>
    </div>
  );
}

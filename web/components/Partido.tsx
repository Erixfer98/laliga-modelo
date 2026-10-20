"use client";
// Piezas de la pantalla de partido: cabecera con equipos, λ, tabla de mercados, cara a cara y hoja de un mercado.
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  api,
  METRICAS,
  type Cfg,
  type Leg,
  type Pata,
  type VistaCara,
} from "@/lib/api";
import type { Compacto, MercadoCorto } from "@/lib/partido";
import { identidadSeleccion } from "@/lib/selecciones";
import { fechaCorta, num, pct, signed } from "@/lib/fmt";
import { Crest } from "./Crest";
import { ListaPartidos } from "./PataDetalle";

const metMin = (met: string) => (METRICAS[met] ?? met).toLowerCase();

// ------------------------------------------------------------------ cabecera
export function Equipos({
  liga,
  equipos,
  local,
  visitante,
  setLocal,
  setVisitante,
}: {
  liga: string;
  equipos: string[];
  local: string;
  visitante: string;
  setLocal: (e: string) => void;
  setVisitante: (e: string) => void;
}) {
  const lados = [
    { nombre: local, label: "local", opciones: equipos, cambiar: setLocal, lado: "l" as const },
    { nombre: visitante, label: "visitante", opciones: equipos.filter((e) => e !== local), cambiar: setVisitante, lado: "v" as const },
  ];
  return (
    <section
      aria-label="Elegir partido"
      className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2 rounded-card bg-card border border-line2 px-3 py-3"
    >
      {lados.map((t, i) => (
        <label
          key={t.label}
          className={`flex items-center gap-2 min-w-0 ${i ? "col-start-3 flex-row-reverse text-right" : ""}`}
        >
          <Crest liga={liga} equipo={t.nombre} size={40} lado={t.lado} />
          <span className="sr-only">Equipo {t.label}</span>
          <select
            aria-label={`Equipo ${t.label}`}
            disabled={!equipos.length}
            value={t.nombre}
            onChange={(e) => t.cambiar(e.target.value)}
            className={`min-w-0 w-full min-h-11 bg-transparent font-extrabold text-[15px] truncate appearance-none ${i ? "text-right" : ""}`}
          >
            {t.opciones.map((e) => (
              <option key={e} value={e}>
                {e}
              </option>
            ))}
          </select>
        </label>
      ))}
      <span className="col-start-2 row-start-1 text-xs font-bold text-mut">vs</span>
    </section>
  );
}

// ------------------------------------------------------------------ λ
export function Lambdas({ d }: { d: Compacto }) {
  const items = [
    { nombre: d.local, valor: d.lambda_local, liga: d.medias_liga.local },
    { nombre: d.visitante, valor: d.lambda_visitante, liga: d.medias_liga.visitante },
    { nombre: "Total", valor: d.lambda_local + d.lambda_visitante, liga: d.medias_liga.total },
  ];
  return (
    <div className="grid grid-cols-3 gap-2" data-testid="lambdas">
      {items.map((x) => (
        <div key={x.nombre} className="rounded-xl bg-card border border-line2 px-2 py-3 text-center min-w-0">
          <div className="text-[11px] font-semibold text-mut truncate">λ {x.nombre}</div>
          <div className="num text-2xl mt-1">{num(x.valor, 2)}</div>
          <div className="text-[11px] text-mut2 mt-1">liga {num(x.liga, 2)}</div>
        </div>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ tabla de mercados
function tituloGrupo(g: string, d: Compacto) {
  if (g === "Total") return `Total de ${metMin(d.metrica)}`;
  if (g === "Resultado")
    return d.metrica === "goles" ? "Resultado" : `Resultado (${metMin(d.metrica).replace("goles ", "")})`;
  if (g === "Mayor número") return `Quién hace más ${metMin(d.metrica)}`;
  return `${METRICAS[d.metrica]} de ${g}`;
}
function etiqueta(m: MercadoCorto) {
  if (m.grupo === "Mayor número") {
    const x = m.mercado.split(": ").pop() ?? m.mercado;
    return x.charAt(0).toUpperCase() + x.slice(1);
  }
  if (m.grupo === "Resultado") return m.mercado;
  return m.mercado.startsWith(m.grupo + " ") ? m.mercado.slice(m.grupo.length + 1) : m.mercado;
}
function Cumple({ x, n }: { x: number; n: number }) {
  const r = n ? x / n : 0;
  const cls = !n ? "text-mut2" : r >= 0.8 ? "text-ok font-extrabold" : r <= 0.2 ? "text-bad" : "";
  return <span className={cls}>{n ? `${x}/${n}` : "—"}</span>;
}
const COLS = "grid grid-cols-[minmax(0,1fr)_3.2rem_3.2rem_2.9rem_2.9rem] gap-1 items-center";

export function TablaMercados({
  d,
  enBoleto,
  abrir,
  masLineas,
}: {
  d: Compacto;
  enBoleto: Set<string>;
  abrir: (m: MercadoCorto) => void;
  masLineas: (grupo: string) => void;
}) {
  const orden = ["Total", d.local, d.visitante, "Resultado", "Mayor número"].filter((g) =>
    d.grupos.includes(g),
  );
  return (
    <div className="space-y-4">
      {orden.map((g) => {
        const filas = d.mercados.filter((m) => m.grupo === g);
        const sinVentaja = filas.every((m) => m.ventaja === "sin ventaja");
        const ou = g === "Total" || g === d.local || g === d.visitante;
        const rango = d.cfg[g]?.[1] ?? 0;
        return (
          <section key={g} aria-label={tituloGrupo(g, d)} className="rounded-card bg-card border border-line2 px-3 pt-3 pb-1">
            <div className="flex items-center justify-between gap-2 mb-1">
              <h2 className="text-sm font-extrabold">{tituloGrupo(g, d)}</h2>
              {sinVentaja && <SinVentaja />}
            </div>
            <div className={`${COLS} text-[11px] text-mut pb-1 border-b border-line2`}>
              <span>Mercado</span>
              <span className="text-right">Prob</span>
              <span className="text-right">Justa</span>
              <span className="flex justify-end" title={d.local}>
                <Crest liga={d.liga} equipo={d.local} size={20} lado="l" />
                <span className="sr-only">{d.local}, últimos {d.n}</span>
              </span>
              <span className="flex justify-end" title={d.visitante}>
                <Crest liga={d.liga} equipo={d.visitante} size={20} lado="v" />
                <span className="sr-only">{d.visitante}, últimos {d.n}</span>
              </span>
            </div>
            <ul>
              {filas.map((m) => (
                <li key={m.mercado} className="border-b border-line2 last:border-0">
                  <button
                    type="button"
                    data-testid="fila-mercado"
                    onClick={() => abrir(m)}
                    aria-label={`${m.mercado}: ${pct(m.prob, 0)}, cuota justa ${m.justa ? num(m.justa) : "no disponible"}, ${d.local} ${m.hl} de ${m.nl}, ${d.visitante} ${m.hv} de ${m.nv}`}
                    className={`${COLS} w-full min-h-11 text-sm text-left hover:bg-card2 -mx-1 px-1 rounded-md`}
                  >
                    <span className="font-semibold leading-tight line-clamp-2 py-1">
                      {enBoleto.has(m.mercado) && <span className="text-acc mr-1" aria-hidden="true">●</span>}
                      {etiqueta(m)}
                    </span>
                    <span className="text-right font-extrabold">{pct(m.prob, 0)}</span>
                    <span className="text-right text-mut">{m.justa ? num(m.justa) : "—"}</span>
                    <span className="text-right"><Cumple x={m.hl} n={m.nl} /></span>
                    <span className="text-right"><Cumple x={m.hv} n={m.nv} /></span>
                  </button>
                </li>
              ))}
            </ul>
            {ou && rango < 4 && (
              <button
                type="button"
                onClick={() => masLineas(g)}
                className="w-full min-h-11 text-xs font-semibold text-acc"
              >
                Más líneas
              </button>
            )}
          </section>
        );
      })}
    </div>
  );
}
/** En la prueba con 2,014 partidos (docs/MODELO_B.md) el modelo no eligió mejor que apostar siempre al lado más común de la liga. */
function SinVentaja() {
  return (
    <span
      className="tag sv"
      title="En la prueba con 2,014 partidos, en este mercado el modelo no eligió mejor que apostar siempre a lo más común de la liga"
    >
      sin ventaja
    </span>
  );
}

// ------------------------------------------------------------------ cara a cara
export function CaraACara({ c, met }: { c: VistaCara | null; met: string }) {
  return (
    <section aria-label="Cara a cara" className="rounded-card bg-card border border-line2 px-3 py-3">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-extrabold">Cara a cara · {metMin(met)}</h2>
        {c && c.n > 0 && (
          <span className="text-xs font-semibold text-mut">
            {c.local}: {c.G}G {c.E}E {c.P}P
          </span>
        )}
      </div>
      {!c ? (
        <div className="h-16 rounded-lg bg-card2 animate-pulse" />
      ) : !c.partidos.length ? (
        <p className="text-sm text-mut py-2">
          No se enfrentaron en {c.torneos.join(" ni ")}.
        </p>
      ) : (
        <ul>
          {c.partidos.map((p) => {
            const v = p.metricas[met];
            return (
              <li key={p.fecha + p.local} className="grid grid-cols-[4.5rem_minmax(0,1fr)] gap-2 py-2 border-b border-line2 last:border-0 text-sm">
                <span className="text-mut text-xs pt-0.5">{fechaCorta(p.fecha)}</span>
                <span className="min-w-0">
                  <span className="block truncate">
                    {p.local} <b className="font-extrabold">{p.goles_local ?? "–"} – {p.goles_visitante ?? "–"}</b> {p.visitante}
                  </span>
                  {met !== "goles" && v && (
                    <span className="block text-xs text-mut">
                      {METRICAS[met]}: <b className="text-txt">{v.local ?? "–"} – {v.visitante ?? "–"}</b>
                    </span>
                  )}
                </span>
              </li>
            );
          })}
        </ul>
      )}
      {c && c.partidos.length > 0 && <p className="text-[11px] text-mut2 mt-2">Torneos {c.torneos.join(" y ")}.</p>}
    </section>
  );
}

// ------------------------------------------------------------------ hoja de un mercado
export function HojaMercado({
  d,
  m,
  cfg,
  boleto,
  addLeg,
  cerrar,
}: {
  d: Compacto;
  m: MercadoCorto;
  cfg?: Cfg;
  boleto: Leg[];
  addLeg: (l: Leg) => void;
  cerrar: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [cuota, setCuota] = useState("");
  const [detalle, setDetalle] = useState<{ p: Pata | null; error: string | null; cargando: boolean }>({ p: null, error: null, cargando: false });
  useEffect(() => {
    if (!ref.current?.open) ref.current?.showModal();
  }, []);
  const c = Number(cuota.replace(",", "."));
  const valida = cuota.trim() !== "" && Number.isFinite(c) && c >= 1.01 && c <= 10000;
  const ev = valida ? m.prob * c + m.push - 1 : null;
  const yaEsta = boleto.some((l) => identidadSeleccion(l.seleccion) === identidadSeleccion(m.seleccion));
  const verDetalle = async () => {
    setDetalle({ p: null, error: null, cargando: true });
    try {
      const p = await api<Pata>(`/liga/${d.liga}/partido`, {
        local: d.local,
        visitante: d.visitante,
        met: d.metrica,
        n: d.n,
        filtro: d.filtro,
        cfg: cfg ? JSON.stringify(cfg) : undefined,
        modo: "detalle",
        pata: m.mercado,
        data_version: d.data_version,
      });
      setDetalle({ p, error: null, cargando: false });
    } catch (e) {
      setDetalle({
        p: null,
        cargando: false,
        error: (e as Error).message.includes("409")
          ? "Los datos se actualizaron. Recargá la página."
          : "No se pudo cargar. Probá de nuevo.",
      });
    }
  };
  const agregar = () => {
    if (!valida || yaEsta) return;
    addLeg({
      partido: d.partido,
      metrica: METRICAS[d.metrica],
      mercado: m.mercado,
      prob: m.prob,
      cuota: c,
      cal: m.tag,
      cls: m.cls,
      lo: m.lo,
      hi: m.hi,
      push: m.push,
      justa: m.justa,
      seleccion: m.seleccion,
    });
  };
  return (
    <dialog
      ref={ref}
      onClose={cerrar}
      onClick={(e) => {
        if (e.target === ref.current) ref.current?.close();
      }}
      aria-labelledby="hoja-titulo"
      className="mt-auto mb-0 mx-auto w-full max-w-lg max-h-[88vh] overflow-y-auto bg-bg text-txt rounded-t-[20px] sm:mb-auto sm:rounded-[20px] p-4 pb-8 border border-line2 backdrop:bg-black/50"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs text-mut">{METRICAS[d.metrica]} · {d.local} vs {d.visitante}</div>
          <h2 id="hoja-titulo" className="text-lg font-extrabold leading-snug mt-1" data-testid="mercado-seleccionado">
            {m.mercado}
          </h2>
        </div>
        <button type="button" aria-label="Cerrar" onClick={() => ref.current?.close()} className="w-11 h-11 shrink-0 rounded-lg bg-card2">
          ✕
        </button>
      </div>
      <dl className="grid grid-cols-2 gap-2 mt-4">
        <div className="rounded-xl bg-card border border-line2 p-3">
          <dt className="text-xs text-mut">Probabilidad</dt>
          <dd className="num text-3xl text-acc mt-1" data-testid="probabilidad-seleccionada">{pct(m.prob, 1)}</dd>
        </div>
        <div className="rounded-xl bg-card border border-line2 p-3">
          <dt className="text-xs text-mut">Cuota justa</dt>
          <dd className="num text-3xl mt-1">{m.justa ? num(m.justa) : "—"}</dd>
        </div>
      </dl>
      <p className="text-sm mt-3">
        Últimos {d.n}{d.filtro === "Todos" ? "" : " (local en casa, visitante fuera)"}:{" "}
        <b>{d.local} {m.hl}/{m.nl}</b> · <b>{d.visitante} {m.hv}/{m.nv}</b>
      </p>
      <label htmlFor="cuota" className="block text-sm font-semibold mt-4">
        Cuota de la casa
      </label>
      <div className="flex gap-2 mt-2">
        <input
          id="cuota"
          className="ctl"
          type="text"
          inputMode="decimal"
          placeholder="1.85"
          autoComplete="off"
          value={cuota}
          onChange={(e) => setCuota(e.target.value)}
        />
        <div className="shrink-0 w-28 rounded-[10px] bg-card border border-line2 flex flex-col justify-center px-3">
          <span className="text-[11px] text-mut">EV</span>
          <span className={`font-extrabold ${ev === null ? "text-mut" : ev > 0 ? "text-ok" : "text-bad"}`} data-testid="ev">
            {ev === null ? "—" : signed(ev)}
          </span>
        </div>
      </div>
      {cuota !== "" && !valida && (
        <p role="alert" className="text-xs text-bad mt-2">Escribí una cuota entre 1.01 y 10000.</p>
      )}
      <button
        type="button"
        onClick={agregar}
        disabled={!valida || yaEsta}
        className="primary w-full min-h-12 rounded-xl text-sm font-bold mt-4 disabled:opacity-50"
      >
        {yaEsta ? "Ya está en tu boleto" : "Agregar al boleto"}
      </button>
      {boleto.length > 0 && (
        <Link href="/boleto" className="min-h-11 flex items-center justify-center text-sm font-semibold text-acc">
          Ver boleto ({boleto.length}) →
        </Link>
      )}
      <div className="border-t border-line2 mt-3 pt-2">
        {!detalle.p && (
          <button type="button" onClick={verDetalle} disabled={detalle.cargando} className="w-full min-h-11 text-sm font-semibold text-mut">
            {detalle.cargando ? "Cargando…" : "Ver partido a partido"}
          </button>
        )}
        {detalle.error && <p role="alert" className="text-xs text-bad">{detalle.error}</p>}
        {detalle.p && (
          <div className="space-y-3 mt-2">
            <ListaPartidos v={d} p={detalle.p} lado="l" />
            <ListaPartidos v={d} p={detalle.p} lado="v" />
          </div>
        )}
      </div>
    </dialog>
  );
}

"use client";
import Link from "next/link";
import { useState, useRef, useEffect } from "react";
import {
  api,
  METRICAS,
  METRICA_CORTA,
  type Cfg,
  type VistaPartido,
} from "@/lib/api";
import { useAnalisis } from "@/lib/useAnalisis";
import { useStore } from "@/lib/store";
import { identidadSeleccion } from "@/lib/selecciones";
import { num, pct, signed } from "@/lib/fmt";
import {
  Btn,
  Card,
  Cargando,
  ErrorBox,
  Kpi,
  Liquidacion,
  Nota,
  Pills,
  Tag,
  Toggle,
} from "@/components/ui";
import { CabeceraPartido, usePartido } from "@/components/Selectores";
import { LambdaSummary } from "@/components/LambdaSummary";
import { LineSelector } from "@/components/LineSelector";
import { EvidenceSummary } from "@/components/EvidenceSummary";
import {
  Chip,
  GraficoModelo,
  HistorialEquipo,
  ListaPartidos,
} from "@/components/PataDetalle";
const NS = [3, 5, 8, 10, 15, 20, 30];
export default function Partido() {
  const { liga, met, setMet, addLeg, boleto } = useStore();
  const { local, visitante, listo } = usePartido();
  const clave = `${liga}|${local}|${visitante}|${met}`;
  const [sel, setSel] = useState<{
    clave: string;
    grupo?: string;
    pata?: string;
    cfg?: Cfg;
  }>({ clave });
  const s = sel.clave === clave ? sel : { clave };
  const [n, setN] = useState(5);
  const [filtro, setFiltro] = useState<"Todos" | "Como jugarán">("Todos");
  const [solo, setSolo] = useState(false);
  const [ajustes, setAjustes] = useState(false);
  const [listaExpandida, setListaExpandida] = useState(false);
  const [precio, setPrecio] = useState({ key: "", value: "" });
  const actual = useRef({ key: "", disponible: false });
  const registro = useRef<AbortController | null>(null);
  const [verificando, setVerificando] = useState("");
  const contextoRegistro = JSON.stringify([clave, s, n, filtro]);
  useEffect(() => () => registro.current?.abort(), [contextoRegistro]);
  actual.current = { key: "", disponible: false };
  const [aviso, setAviso] = useState({ key: "", texto: "" });
  const {
    v,
    mercado,
    p: detalle,
    error,
    loading,
    reintentar,
    detalle: estadoDetalle,
  } = useAnalisis(
    listo ? `/liga/${liga}/partido` : null,
    {
      local,
      visitante,
      met,
      n,
      filtro,
      cfg: s.cfg ? JSON.stringify(s.cfg) : undefined,
    },
    s.grupo,
    s.pata,
  );
  const cabecera = (
    <>
      <div className="flex justify-between items-end mb-5">
        <div>
          <div className="eyebrow mb-2">Análisis del enfrentamiento</div>
          <h1 className="page-title">
            {local && visitante
              ? `${local} vs ${visitante}`
              : "Analiza un enfrentamiento"}
          </h1>
        </div>
        <Link
          href="/cara"
          className="hidden sm:flex text-sm font-semibold text-acc min-h-11 items-center"
        >
          Cara a cara →
        </Link>
      </div>
      <CabeceraPartido sub="Análisis del enfrentamiento elegido, con el histórico disponible." />
      <Pills
        label="Métrica del análisis"
        opciones={Object.keys(METRICAS)}
        valor={met}
        onChange={setMet}
        format={(m) => METRICA_CORTA[m]}
        className="mb-5"
      />
    </>
  );
  if (error)
    return (
      <>
        {cabecera}
        <ErrorBox error={error} reintentar={reintentar} />
      </>
    );
  if (
    !v ||
    v.liga !== liga ||
    v.local !== local ||
    v.visitante !== visitante ||
    v.metrica !== met
  )
    return (
      <>
        {cabecera}
        <Cargando alto={320} />
      </>
    );
  const grupo = s.grupo && v.grupos.includes(s.grupo) ? s.grupo : v.grupos[0];
  const p = mercado!;
  const lista = v.mercados.filter(
    (m) => m.grupo === grupo && (!solo || m.cls === "exc" || m.cls === "bue"),
  );
  const conLineas = !["Resultado", "Mayor número"].includes(grupo);
  const [centro, rango] = (s.cfg ?? v.cfg)[grupo] ?? [0.5, 1];
  const quoteKey = `${clave}|${p.mercado}`;
  const cuota = precio.key === quoteKey ? precio.value : "";
  const cuotaN = Number(cuota) || 0;
  const cuotaValida =
    cuota.trim() !== "" &&
    Number.isFinite(cuotaN) &&
    cuotaN >= 1.01 &&
    cuotaN <= 10000;
  // Fórmulas vigentes, sin cambios: cada escenario conserva su probabilidad y push.
  const ev = cuotaValida ? p.prob * cuotaN + p.push - 1 : null;
  const evLo = cuotaValida
    ? Math.min(...p.escenarios.map((e) => e.prob * cuotaN + e.push - 1))
    : null;
  const duplicada = boleto.some(
    (l) => identidadSeleccion(l.seleccion) === identidadSeleccion(p.seleccion),
  );
  const cambiarGrupo = (g: string) =>
    setSel({ clave, cfg: s.cfg, grupo: g, pata: undefined });
  const cambiarLineas = (c: number, r: number) =>
    setSel({
      clave,
      cfg: { ...(s.cfg ?? v.cfg), [grupo]: [c, r] },
      grupo,
      pata: undefined,
    });
  const registroKey = JSON.stringify([
    contextoRegistro,
    p.mercado,
    v.data_version,
    cuota,
  ]);
  actual.current = {
    key: registroKey,
    disponible:
      cuotaValida &&
      !loading &&
      !duplicada &&
      !estadoDetalle.error &&
      !estadoDetalle.loading,
  };
  const agregar = async () => {
    if (
      !cuotaValida ||
      loading ||
      duplicada ||
      estadoDetalle.error ||
      estadoDetalle.loading
    )
      return;
    if (verificando === registroKey) return;
    const controller = new AbortController();
    registro.current?.abort();
    registro.current = controller;
    setVerificando(registroKey);
    try {
      await api(
        `/liga/${liga}/partido`,
        {
          local,
          visitante,
          met,
          modo: "version",
          data_version: v.data_version,
        },
        controller.signal,
      );
      if (
        controller.signal.aborted ||
        actual.current.key !== registroKey ||
        !actual.current.disponible
      )
        return;
      addLeg({
        partido: v.partido,
        metrica: METRICAS[met],
        mercado: p.mercado,
        prob: p.prob,
        cuota: cuotaN,
        cal: p.tag,
        cls: p.cls,
        lo: p.lo,
        hi: p.hi,
        push: p.push,
        justa: p.justa,
        seleccion: p.seleccion,
      });
      setAviso({
        key: quoteKey,
        texto: "Selección añadida. Puedes revisarla en tu boleto.",
      });
    } catch (e) {
      if (!controller.signal.aborted && actual.current.key === registroKey) {
        setAviso({
          key: quoteKey,
          texto: (e as Error).message.includes("409")
            ? "El análisis cambió antes de añadir. Actualiza los datos e inténtalo de nuevo."
            : "No pudimos verificar la selección. Inténtalo de nuevo.",
        });
        reintentar();
      }
    } finally {
      setVerificando((previous) => (previous === registroKey ? "" : previous));
    }
  };
  return (
    <>
      {cabecera}
      <LambdaSummary v={v} />
      <nav aria-label="Secciones del análisis" className="flex flex-wrap gap-2 mb-5 text-xs font-bold">
        <a className="min-h-11 inline-flex items-center px-3 rounded-lg bg-card border border-line2" href="#expectativa">01 · Lambdas</a>
        <a className="min-h-11 inline-flex items-center px-3 rounded-lg bg-card border border-line2" href="#mercados">02 · Líneas</a>
        <a className="min-h-11 inline-flex items-center px-3 rounded-lg bg-card border border-line2" href="#distribucion">03 · Distribución</a>
        <a className="min-h-11 inline-flex items-center px-3 rounded-lg bg-card border border-line2" href="#evidencia">04 · Evidencia</a>
        <a className="min-h-11 inline-flex items-center px-3 rounded-lg bg-card border border-line2" href="#seleccion">05 · Decidir</a>
      </nav>
      <div className="grid lg:grid-cols-[minmax(0,1.8fr)_minmax(275px,0.75fr)] gap-5 items-start">
        <div id="mercados" className="min-w-0 scroll-mt-36 lg:col-start-1 lg:row-start-1">
          <Card
            titulo="02 · Explorá escenarios y líneas"
            desc="Elegí una categoría, línea y dirección. Las probabilidades siempre vienen del motor, no del historial."
          >
            {loading && (
              <p role="status" className="text-xs text-mut">
                Actualizando mercados…
              </p>
            )}
            <Pills
              label="Grupo de mercados"
              opciones={v.grupos}
              valor={grupo}
              onChange={cambiarGrupo}
              small
            />
            <div className="mt-4">
              <LineSelector
                grupo={grupo}
                mercados={v.mercados}
                elegido={p.mercado}
                loading={loading}
                onSelect={(mercado) => setSel({ clave, cfg: s.cfg, grupo, pata: mercado })}
                onExtend={(linea, over) => {
                  const cfg = s.cfg ?? v.cfg;
                  const [centro, rango] = cfg[grupo];
                  const abajo = centro - rango, arriba = centro + rango;
                  const nuevoCentro = linea > arriba ? centro + (linea - arriba)
                    : linea < abajo ? centro - (abajo - linea) : centro;
                  setSel({
                    clave, grupo,
                    cfg: { ...cfg, [grupo]: [nuevoCentro, rango] },
                    pata: grupo + " " + (over ? "Over" : "Under") + " " + linea,
                  });
                }}
              />
            </div>
            <div aria-live="polite" className="rounded-xl border border-line2 px-4 py-3 mb-4">
              <div className="text-xs text-mut mb-1">Selección actual</div>
              <div className="flex items-center justify-between gap-3">
                <span className="font-extrabold text-sm sm:text-base">{p.mercado}</span>
                <span className="num text-2xl text-acc">{loading ? "…" : pct(p.prob, 1)}</span>
              </div>
              <p className="text-xs text-mut mt-2">Cuota justa {num(p.justa)} · Sensibilidad {pct(p.lo, 1)}–{pct(p.hi, 1)} · Devolución {pct(p.push, 1)}</p>
            </div>
            <details
              className="mt-3 mb-4"
              open={ajustes}
              onToggle={(e) => setAjustes(e.currentTarget.open)}
            >
              <summary className="flex min-h-11 items-center justify-between text-xs font-semibold text-mut">
                Ajustar líneas e historial (avanzado) <span aria-hidden="true">⌄</span>
              </summary>
              <div className="grid sm:grid-cols-2 gap-3 pt-3">
                {conLineas && (
                  <>
                    <div>
                      <div className="eyebrow mb-2">Línea central</div>
                      <div className="flex items-center justify-between rounded-xl border border-line">
                        <button
                          aria-label="Reducir línea"
                          onClick={() =>
                            cambiarLineas(Math.max(centro - 1, 0.5), rango)
                          }
                          className="min-w-12 min-h-12"
                        >
                          −
                        </button>
                        <span className="font-bold">{centro}</span>
                        <button
                          aria-label="Aumentar línea"
                          onClick={() =>
                            cambiarLineas(Math.min(centro + 1, 60.5), rango)
                          }
                          className="min-w-12 min-h-12"
                        >
                          +
                        </button>
                      </div>
                    </div>
                    <label className="text-xs text-mut">
                      Líneas alrededor
                      <select
                        aria-label="Líneas alrededor"
                        className="ctl mt-2"
                        value={rango}
                        onChange={(e) =>
                          cambiarLineas(centro, Number(e.target.value))
                        }
                      >
                        {[0, 1, 2, 3, 4].map((r) => (
                          <option key={r} value={r}>
                            ± {r} líneas
                          </option>
                        ))}
                      </select>
                    </label>
                  </>
                )}
                <label className="text-xs text-mut">
                  Historial de cada equipo
                  <select
                    className="ctl mt-2"
                    aria-label="Número de partidos históricos"
                    value={n}
                    onChange={(e) => setN(Number(e.target.value))}
                  >
                    {NS.map((x) => (
                      <option key={x} value={x}>
                        Últimos {x} partidos
                      </option>
                    ))}
                  </select>
                </label>
                <div className="space-y-1">
                  <Toggle
                    label="Solo en su condición de local/visitante"
                    valor={filtro !== "Todos"}
                    onChange={(x) => setFiltro(x ? "Como jugarán" : "Todos")}
                  />
                  <Toggle
                    label="Calificación Buena o mejor"
                    valor={solo}
                    onChange={setSolo}
                  />
                </div>
              </div>
            </details>
            <details className="border-t border-line2 mt-4 pt-2"
              open={listaExpandida} onToggle={(e) => setListaExpandida(e.currentTarget.open)}>
              <summary className="min-h-12 flex items-center justify-between gap-3 text-sm font-semibold text-acc">
                <span>Ver lista completa de mercados</span>
                <span className="text-xs text-mut">{lista.length} opciones</span>
              </summary>
              <div className="pt-2">
            <div className="flex justify-between text-xs text-mut pb-2">
              <span>Mercado</span>
              <span>Probabilidad del modelo</span>
            </div>
            <div
              className="divide-y divide-line2"
              role="group"
              aria-label="Seleccionar mercado"
            >
              {lista.map((m) => {
                const active = m.mercado === p.mercado;
                return (
                  <button
                    key={m.mercado}
                    disabled={loading}
                    aria-pressed={active}
                    onClick={() =>
                      setSel({ clave, cfg: s.cfg, grupo, pata: m.mercado })
                    }
                    className={`w-full min-h-[86px] text-left flex items-center justify-between gap-3 p-3 rounded-lg ${active ? "bg-card2 border-l-[3px] border-acc" : "border-l-[3px] border-transparent hover:bg-card2"}`}
                  >
                    <div className="min-w-0">
                      <div className="font-bold text-sm leading-snug">
                        {m.mercado}
                      </div>
                      <div className="text-xs text-mut mt-2">
                        Cuota justa {num(m.justa)}
                      </div>
                      <div
                        className="text-xs text-mut mt-1 leading-relaxed"
                        data-testid="historico-mercado"
                      >
                        <span className="block">Cumplimiento histórico</span>
                        <span className="inline-block mr-2">
                          {local}: {m.hl} de {m.nl}{" "}
                          {m.nl === 1 ? "partido" : "partidos"}
                        </span>
                        <span className="inline-block">
                          {visitante}: {m.hv} de {m.nv}{" "}
                          {m.nv === 1 ? "partido" : "partidos"}
                        </span>
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="num text-2xl text-acc">
                        {pct(m.prob, 1)}
                      </div>
                      <div className="text-[.7rem] text-mut mt-2">
                        {pct(m.lo, 1)}–{pct(m.hi, 1)}*
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
            {!lista.length && (
              <div role="status" className="py-6 text-sm text-mut">
                No hay mercados con esa calificación. Desactiva el filtro o
                ajusta las líneas.
              </div>
            )}
            <Nota>
              * Sensibilidad heurística del modelo. No es un intervalo de
              confianza validado.
            </Nota>
              </div>
            </details>
          </Card>
        </div>

      <section id="distribucion" className="mt-4 min-w-0 scroll-mt-36 lg:col-start-1" aria-label="Distribución de probabilidades">
        <Card titulo="03 · Cómo se distribuyen los resultados"
          desc="Cada escenario corresponde a la selección activa. El gráfico proviene del motor y distingue aciertos y devoluciones cuando corresponde.">
          {estadoDetalle.error ? (
            <p role="status" className="text-sm text-mut py-4">La distribución no está disponible hasta verificar nuevamente este mercado.</p>
          ) : !loading && detalle ? (
            <GraficoModelo v={v} p={detalle} />
          ) : (
            <p role="status" className="text-sm text-mut py-4">Preparando la distribución de la selección…</p>
          )}
        </Card>
      </section>
      <div className="min-w-0 lg:col-start-1">
      {loading ? (
        <section id="evidencia" role="status" className="rounded-card bg-card border border-line2 p-5 mt-5 text-sm text-mut">Actualizando la evidencia de la nueva selección…</section>
      ) : (
        <EvidenceSummary v={v} p={p} n={n} filtro={filtro} />
      )}
      </div>
        <aside id="seleccion" className="min-w-0 lg:col-start-2 lg:row-start-1 lg:row-span-3 lg:sticky lg:top-[145px] lg:self-start scroll-mt-36">
          <Card
            className="match-stripe"
            titulo="Tu selección"
            right={<span className="tag">{METRICA_CORTA[met]}</span>}
          >
            <h2
              className="text-xl font-extrabold tracking-tight leading-snug"
              data-testid="mercado-seleccionado"
            >
              {p.mercado}
            </h2>
            <div className="flex items-end gap-2 mt-5 mb-4">
              <span
                className="num text-5xl text-acc"
                data-testid="probabilidad-seleccionada"
              >
                {loading ? "…" : pct(p.prob, 1)}
              </span>
              <span className="text-xs text-mut mb-1">
                de acierto
                <br />
                según el modelo
              </span>
            </div>
            <Liquidacion prob={p.prob} push={p.push} loss={p.loss} />
            <dl className="border-t border-line2 mt-5 pt-4 flex justify-between text-sm">
              <dt className="text-mut">Cuota justa</dt>
              <dd className="font-bold">{num(p.justa)}</dd>
            </dl>
            <details className="mt-3">
              <summary className="flex items-center justify-between min-h-11 text-xs text-mut">
                Histórico y sensibilidad <span aria-hidden="true">⌄</span>
              </summary>
              <div className="text-xs text-mut leading-relaxed space-y-2">
                <p>
                  Cumplimiento histórico: <b>{pct(p.tasa, 1)}</b> ({p.hl + p.hv}{" "}
                  de {p.nl + p.nv} {p.nl + p.nv === 1 ? "partido" : "partidos"}
                  ). Las devoluciones no son aciertos.
                </p>
                <p>
                  {local}: {p.hl} de {p.nl}{" "}
                  {p.nl === 1 ? "partido" : "partidos"}. {visitante}: {p.hv} de{" "}
                  {p.nv} {p.nv === 1 ? "partido" : "partidos"}.
                </p>
                <p>
                  Sensibilidad heurística: {pct(p.lo, 1)}–{pct(p.hi, 1)}. Sin
                  cobertura estadística validada.
                </p>
                <p>
                  Calificación orientativa: <Tag cls={p.cls}>{p.tag}</Tag>
                </p>
              </div>
            </details>
            <div className="border-t border-line2 mt-4 pt-4">
              <label htmlFor="cuota" className="text-sm font-semibold">
                Tu cuota decimal
              </label>
              <p className="text-xs text-mut mt-1 mb-3">
                Introduce la cuota que has consultado. Kuota no proporciona
                precios de casas.
              </p>
              <input
                id="cuota"
                className="ctl"
                type="number"
                inputMode="decimal"
                step="0.01"
                min="1.01"
                max="10000"
                placeholder="Sin cuota introducida"
                value={cuota}
                onChange={(e) =>
                  setPrecio({ key: quoteKey, value: e.target.value })
                }
              />
              {cuota !== "" && !cuotaValida && (
                <p role="alert" className="text-xs text-bad mt-2">
                  Introduce una cuota entre 1,01 y 10.000.
                </p>
              )}
              {cuotaValida ? (
                <div className="mt-3">
                  <Kpi
                    items={[
                      {
                        label: "EV modelo",
                        valor: signed(ev),
                        cls: (ev ?? 0) > 0 ? "text-ok" : "text-bad",
                      },
                      {
                        label: "EV mínimo",
                        valor: signed(evLo),
                        sub: "escenarios de sensibilidad",
                        cls: (evLo ?? 0) > 0 ? "text-ok" : "text-bad",
                      },
                    ]}
                  />
                  <Nota>
                    EV = acierto × cuota + devolución − 1. Un EV positivo
                    estimado no garantiza rentabilidad.
                  </Nota>
                </div>
              ) : (
                <p className="text-xs text-mut mt-3">
                  El valor esperado estará disponible al introducir una cuota
                  válida.
                </p>
              )}
              <Btn
                primary
                disabled={
                  !cuotaValida ||
                  loading ||
                  duplicada ||
                  !!estadoDetalle.error ||
                  estadoDetalle.loading ||
                  verificando === registroKey
                }
                onClick={agregar}
                className="w-full mt-4"
              >
                {duplicada ? "Ya está en tu boleto" : "Añadir al boleto"}
              </Btn>
              <div
                role="status"
                aria-live="polite"
                className="text-xs text-mut mt-3"
              >
                {aviso.key === quoteKey && aviso.texto}
              </div>
              {boleto.length > 0 && (
                <Link
                  href="/boleto"
                  className="min-h-11 flex items-center justify-center text-sm font-semibold text-acc"
                >
                  Revisar boleto ({boleto.length}) →
                </Link>
              )}
            </div>
          </Card>
          <Link
            href="/cara"
            className="flex items-center justify-between min-h-12 text-sm text-mut font-semibold px-2"
          >
            Explorar el cara a cara <span aria-hidden="true">→</span>
          </Link>
          <p className="text-xs leading-relaxed text-mut px-2 mt-4">
            Una probabilidad alta no es una garantía. El análisis se basa en
            datos históricos y sus limitaciones.
          </p>
        </aside>
      </div>
      <div className="w-full mt-5">
        {estadoDetalle.loading && (
          <p role="status" className="text-xs text-mut">
            Actualizando detalle histórico…
          </p>
        )}
        {estadoDetalle.error && (
          <ErrorBox
            error={estadoDetalle.error}
            reintentar={() => {
              reintentar();
              estadoDetalle.reintentar();
            }}
          />
        )}{" "}
        <details className="disclosure">
          <summary>Historial y comparación de equipos</summary>
          <div className="disclosure-body">
            <p className="text-xs text-mut mb-4">
              Últimos {n} partidos por equipo ·{" "}
              {filtro === "Todos"
                ? "todas las condiciones"
                : "local en casa y visitante fuera"}
              . Es contexto histórico, no una probabilidad futura.
            </p>
            {detalle && <HistorialEquipo v={v} p={detalle} lado="l" />}
            {detalle && <HistorialEquipo v={v} p={detalle} lado="v" />}
          </div>
        </details>
        <details className="disclosure">
          <summary>Partido a partido</summary>
          <div className="disclosure-body">
            {detalle && <ListaPartidos v={v} p={detalle} lado="l" />}
            {detalle && <ListaPartidos v={v} p={detalle} lado="v" />}
          </div>
        </details>
        <details className="disclosure">
          <summary>Parámetros y sensibilidad del modelo</summary>
          <div className="disclosure-body">
            <p className="text-xs text-mut mb-4">
              λ es la cantidad esperada, no un resultado asegurado. Rangos
              heurísticos con cobertura no validada; no incluyen lesiones,
              alineaciones ni árbitro.
            </p>
            <div className="space-y-4">
              {[
                {
                  name: v.local,
                  lam: v.lambda_local,
                  range: v.rango.local,
                  media: v.medias_liga.local,
                  vari: v.var.local,
                },
                {
                  name: v.visitante,
                  lam: v.lambda_visitante,
                  range: v.rango.visitante,
                  media: v.medias_liga.visitante,
                  vari: v.var.visitante,
                },
                {
                  name: "Total",
                  lam: v.lambda_local + v.lambda_visitante,
                  range: v.rango.total,
                  media: v.medias_liga.total,
                  vari: null,
                },
              ].map((r) => (
                <div
                  key={r.name}
                  className="border-b border-line2 pb-3 text-sm"
                >
                  <div className="flex justify-between font-semibold">
                    <span>{r.name}</span>
                    <span>λ {num(r.lam)}</span>
                  </div>
                  <div className="text-xs text-mut mt-2 flex flex-wrap gap-2">
                    <span>
                      Sensibilidad {num(r.range[0])}–{num(r.range[1])}
                    </span>
                    <span>Media liga {num(r.media)}</span>
                    {r.vari && <Chip {...r.vari} />}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </details>
      </div>

          <div className="num text-xl text-acc">
            {loading ? "…" : pct(p.prob, 1)}
          </div>
          <span className="text-xs text-mut">Ver →</span>
        </a>
      </div>
      <p className="text-xs text-mut mt-6">
        Datos: football-data.co.uk y ESPN · Tiempo reglamentario.
      </p>
    </>
  );
}

"use client";
import Link from "next/link";
import { useState } from "react";
import { METRICAS, METRICA_CORTA, type VistaInicio } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { useStore } from "@/lib/store";
import { fechaLarga, num, pct, resumenLocal, signed } from "@/lib/fmt";
import { Bar, Card, Cargando, ErrorBox, Nota, Pills, T } from "@/components/ui";
import { Crest } from "@/components/Crest";
import { CabeceraPartido } from "@/components/Selectores";
import { TablaPosiciones } from "@/components/Tabla";
export default function Inicio() {
  const { liga, boleto } = useStore();
  const [met, setMet] = useState("corners");
  const [pulsoExpandido, setPulsoExpandido] = useState<string | null>(null);
  const expandido = pulsoExpandido === liga;
  const {
    data: v,
    error,
    reintentar,
  } = useApi<VistaInicio>(`/liga/${liga}`, { tendencias: met });
  const rb = resumenLocal(boleto);
  return (
    <>
      <div className="flex items-end justify-between gap-3 mb-6">
        <div>
          <div className="eyebrow mb-2">Tu mirada al juego</div>
          <h1 className="page-title">El fútbol, con perspectiva.</h1>
          <p className="text-sm text-mut mt-2">
            Elige un enfrentamiento. Explora sus probabilidades.
          </p>
        </div>
        <span className="hidden lg:block text-xs text-mut">
          6 ligas · análisis con datos
        </span>
      </div>
      <div className="grid lg:grid-cols-[minmax(0,1.6fr)_minmax(280px,1fr)] gap-6">
        <div className="min-w-0">
          <CabeceraPartido />
          <Link
            href="/partido"
            className="primary flex items-center justify-between rounded-xl min-h-14 px-5 font-bold text-sm mb-6"
          >
            Analizar enfrentamiento <span aria-hidden="true">→</span>
          </Link>
          {error ? (
            <ErrorBox error={error} reintentar={reintentar} />
          ) : !v ? (
            <Cargando alto={280} />
          ) : (
            <Card
              titulo="Pulso de la liga"
              desc="Medias descriptivas de los últimos cinco partidos registrados de cada equipo. No son probabilidades ni recomendaciones de apuesta."
            >
              <Pills
                label="Métrica de tendencias"
                opciones={Object.keys(METRICAS)}
                valor={met}
                onChange={setMet}
                format={(m) => METRICA_CORTA[m]}
                small
              />
              <div className="flex justify-between mt-5 mb-3 text-xs text-mut">
                <span>{METRICAS[v.tendencias.metrica]} por partido</span>
                <span>Media de la liga {num(v.tendencias.media_liga, 1)}</span>
              </div>
              <div id="pulso-equipos">
                {v.tendencias.filas.map((f, index) => (
                  <div
                    key={f.equipo}
                    data-testid="equipo-pulso"
                    className={`border-t border-line2 py-3 ${index >= 5 && !expandido ? "hidden lg:block" : ""}`}
                  >
                    <div className="flex items-center gap-3">
                      <Crest liga={liga} equipo={f.equipo} size={32} />
                      <div className="flex-1 min-w-0 font-semibold text-sm truncate">
                        {f.equipo}
                      </div>
                      <div className="num text-lg">{num(f.prom, 1)}</div>
                      <span className="text-xs text-mut min-w-10 text-right">
                        {signed(f.prom - v.tendencias.media_liga, 1)}
                      </span>
                    </div>
                    <Bar
                      valor={f.prom}
                      marca={v.tendencias.media_liga}
                      max={
                        Math.max(
                          ...v.tendencias.filas.map((f) => f.prom),
                          v.tendencias.media_liga,
                        ) * 1.1
                      }
                      color="var(--acc)"
                      alto={4}
                    />
                    <div className="text-xs text-mut">
                      A favor {num(f.favor, 1)} · en contra {num(f.contra, 1)}
                    </div>
                  </div>
                ))}
              </div>
              {v.tendencias.filas.length > 5 && (
                <button
                  type="button"
                  aria-expanded={expandido}
                  aria-controls="pulso-equipos"
                  onClick={() => setPulsoExpandido(expandido ? null : liga)}
                  className="lg:hidden w-full min-h-12 mt-2 rounded-xl border border-line text-sm font-semibold text-acc"
                >
                  {expandido
                    ? "Mostrar solo cinco equipos"
                    : `Ver los ${v.tendencias.filas.length} equipos`}
                </button>
              )}
            </Card>
          )}
        </div>
        <aside className="min-w-0">
          {rb && (
            <Link href="/boleto" className="block">
              <Card
                titulo="Tu boleto"
                right={<span className="text-sm text-acc">Ver →</span>}
              >
                <div className="flex justify-between items-end">
                  <div>
                    <div className="num text-3xl">{rb.n}</div>
                    <div className="text-xs text-mut mt-2">
                      {rb.n === 1
                        ? "selección guardada"
                        : "selecciones guardadas"}
                    </div>
                  </div>
                  <div className="text-right">
                    <T>Producto de cuotas</T>
                    <div className="num text-xl mt-2">{num(rb.cuota)}</div>
                  </div>
                </div>
                <Nota>
                  Abre el boleto para consultar probabilidad conjunta,
                  devoluciones y valor esperado calculados por el motor.
                </Nota>
              </Card>
            </Link>
          )}
          {v && (
            <>
              <Card
                titulo="En contexto"
                right={<span className="tag">{v.temporada}</span>}
              >
                <dl className="grid grid-cols-3 gap-3">
                  <div>
                    <dt className="text-xs text-mut">Partidos</dt>
                    <dd className="num text-xl mt-2">{v.partidos_temporada}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-mut">Equipos</dt>
                    <dd className="num text-xl mt-2">{v.equipos.length}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-mut">Histórico</dt>
                    <dd className="num text-xl mt-2">{v.partidos_total}</dd>
                  </div>
                </dl>
                <Nota>
                  Último partido registrado: <b>{fechaLarga(v.ultimo)}</b>.{" "}
                  {v.validacion && (
                    <span>
                      {v.validacion.ok
                        ? "Validación estructural correcta."
                        : "La base presenta incidencias."}{" "}
                      {v.validacion.avisos.length > 0 &&
                        (v.validacion.avisos.length === 1
                          ? "Hay un aviso de calidad."
                          : "Hay avisos de calidad.")}
                    </span>
                  )}
                </Nota>
                <details className="mt-3">
                  <summary className="text-xs text-mut min-h-11 flex items-center">
                    Procedencia y calidad de los datos
                  </summary>
                  <p className="text-xs text-mut leading-relaxed">
                    football-data.co.uk (Europa) y ESPN (Liga MX). Temporadas:{" "}
                    {v.torneos_recientes.join(", ")}. La validación estructural
                    no certifica vigencia ni completitud.
                  </p>
                  {v.validacion &&
                    [...v.validacion.errores, ...v.validacion.avisos].map(
                      (t, i) => (
                        <p key={i} className="text-xs mt-2 text-mut">
                          {t}
                        </p>
                      ),
                    )}
                </details>
              </Card>
              <Card
                titulo="Clasificación"
                right={
                  <Link
                    className="text-xs text-acc min-h-11 flex items-center"
                    href="/tabla"
                  >
                    Ver tabla →
                  </Link>
                }
              >
                <TablaPosiciones
                  liga={liga}
                  filas={v.tabla.slice(0, 6)}
                  compacta
                />
              </Card>
              <details className="disclosure">
                <summary>Medias de la liga</summary>
                <div className="disclosure-body">
                  {v.medias.map((m) => (
                    <div
                      key={m.metrica}
                      className="py-3 border-b border-line2 last:border-0"
                    >
                      <div className="flex justify-between font-semibold text-sm">
                        <span>{m.nombre}</span>
                        <span>{num(m.total, m.decimales)} total</span>
                      </div>
                      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-mut">
                        <span>Local {num(m.local, m.decimales)}</span>
                        <span>Visitante {num(m.visitante, m.decimales)}</span>
                        <span>
                          Over {m.linea}: {pct(m.pct_over)}
                        </span>
                      </div>
                    </div>
                  ))}
                  <Nota>
                    Frecuencias históricas de la liga; no son predicciones del
                    enfrentamiento.
                  </Nota>
                </div>
              </details>
            </>
          )}
        </aside>
      </div>
    </>
  );
}

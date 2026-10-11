"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiPost, type ResumenBoleto, type Stake } from "@/lib/api";
import { useStore } from "@/lib/store";
import { gruposBoleto } from "@/lib/selecciones";
import { num, pct, q, signed } from "@/lib/fmt";
import { Btn, Card, Cargando, Kpi, Nota, T } from "@/components/ui";
import { Crest } from "@/components/Crest";
export default function Boleto() {
  const { boleto, removeLeg, vaciar, banca, setBanca, listo } = useStore();
  const [revision, setRevision] = useState(0);
  const [res, setRes] = useState<{
    resumen: ResumenBoleto;
    stake: Stake;
    clave: string;
  } | null>(null);
  const [error, setError] = useState<{ clave: string; message: string } | null>(
    null,
  );
  const [confirm, setConfirm] = useState(false);
  const clave = JSON.stringify({ patas: boleto, banca, revision });
  useEffect(() => {
    if (!listo || !boleto.length) return;
    const controller = new AbortController();
    setRes(null);
    setError(null);
    apiPost<{ resumen: ResumenBoleto; stake: Stake }>(
      "/boleto",
      { patas: boleto, banca },
      controller.signal,
    )
      .then((r) => {
        if (!controller.signal.aborted) setRes({ ...r, clave });
      })
      .catch((e: Error) => {
        if (!controller.signal.aborted) setError({ clave, message: e.message });
      });
    return () => controller.abort();
  }, [boleto, banca, listo, clave]);
  if (!listo) return <Cargando alto={240} />;
  const actual = res?.clave === clave ? res : null;
  const rb = actual?.resumen;
  const stk = actual?.stake;
  const fail = error?.clave === clave;
  return (
    <>
      <div className="flex justify-between items-end gap-3 mb-6">
        <div>
          <div className="eyebrow mb-2">Selecciones, en perspectiva</div>
          <h1 className="page-title">Tu boleto.</h1>
          <p className="text-sm text-mut mt-2">
            {boleto.length
              ? `${boleto.length} ${boleto.length === 1 ? "selección" : "selecciones"} · boleto guardado en este dispositivo`
              : "Añade mercados para consultar la probabilidad conjunta y el valor esperado de tu boleto."}
          </p>
        </div>
        {boleto.length > 0 && (
          <Link
            href="/partido"
            className="hidden sm:flex items-center min-h-11 text-sm font-semibold text-acc"
          >
            Añadir selección →
          </Link>
        )}
      </div>
      {!boleto.length ? (
        <section className="bg-card border border-line2 rounded-card py-14 px-6 text-center max-w-2xl mx-auto">
          <div aria-hidden="true" className="text-5xl text-mut mb-5">
            ◇
          </div>
          <h2 className="text-xl font-bold">Tu boleto está vacío</h2>
          <p className="text-sm leading-relaxed text-mut mt-3 max-w-sm mx-auto">
            Explora un enfrentamiento, elige un mercado e introduce tu cuota.
            Aquí podrás revisar cómo se comportan tus selecciones juntas.
          </p>
          <Link
            href="/partido"
            className="primary rounded-xl inline-flex min-h-12 items-center px-5 text-sm font-bold mt-6"
          >
            Explorar mercados →
          </Link>
        </section>
      ) : (
        <div className="grid lg:grid-cols-[minmax(0,1.65fr)_minmax(320px,1fr)] gap-6 items-start">
          <div className="min-w-0">
            {gruposBoleto(boleto).map((g, gi) => (
              <section
                key={gi}
                className="rounded-card bg-card border border-line2 mb-4 overflow-hidden"
                aria-label={g.nombre}
              >
                <div className="px-4 py-4 border-b border-line2 flex items-center gap-3">
                  {g.liga && g.local && g.visitante && (
                    <div className="flex -space-x-1">
                      <Crest liga={g.liga} equipo={g.local} size={32} />
                      <Crest liga={g.liga} equipo={g.visitante} size={32} />
                    </div>
                  )}
                  <h2 className="text-sm font-bold leading-relaxed">
                    {g.nombre}
                  </h2>
                </div>
                {g.legs.map(({ leg: l, index }) => (
                  <div
                    key={index}
                    className="flex items-start gap-3 px-4 py-5 border-b border-line2 last:border-0"
                    data-testid="seleccion-boleto"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="eyebrow text-[.65rem]! mb-2">
                        {l.metrica}
                      </div>
                      <div className="font-bold text-base leading-snug">
                        {l.mercado}
                      </div>
                      <div className="flex gap-4 mt-3 text-xs text-mut">
                        <span>
                          Cuota introducida{" "}
                          <b className="text-txt">{num(l.cuota)}</b>
                        </span>
                        <span>
                          Modelo al añadir{" "}
                          <b className="text-txt">{pct(l.prob, 1)}</b>
                        </span>
                      </div>
                      <details className="mt-2">
                        <summary className="text-xs text-mut min-h-11 flex items-center">
                          Detalles guardados
                        </summary>
                        <p className="text-xs text-mut leading-relaxed">
                          Cuota justa {num(l.justa)} · sensibilidad heurística{" "}
                          {pct(l.lo, 1)}–{pct(l.hi, 1)} · devolución{" "}
                          {pct(l.push ?? null, 1)} · calificación orientativa{" "}
                          {l.cal}.{" "}
                          {l.seleccion
                            ? `Versión ${l.seleccion.version}.`
                            : "Selección antigua: vuelve a añadirla para calcular el conjunto."}
                        </p>
                      </details>
                    </div>
                    <button
                      onClick={() => removeLeg(index)}
                      aria-label={`Quitar ${l.mercado}`}
                      className="shrink-0 w-11 h-11 rounded-lg bg-card2 text-mut"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </section>
            ))}
            <div className="flex flex-wrap items-center gap-3 mt-4">
              <Link
                href="/partido"
                className="flex-1 min-w-[180px] rounded-xl border border-line min-h-12 flex justify-center items-center text-sm font-semibold"
              >
                + Añadir selección
              </Link>
              <button
                onClick={() => setConfirm(true)}
                className="min-h-12 px-3 text-sm text-mut"
              >
                Vaciar boleto
              </button>
            </div>
            {confirm && (
              <div
                role="alert"
                className="bg-card border border-line rounded-xl p-4 mt-3"
              >
                <p className="text-sm font-semibold">
                  ¿Eliminar todas las selecciones guardadas?
                </p>
                <div className="flex gap-3 mt-3">
                  <Btn
                    onClick={() => {
                      vaciar();
                      setConfirm(false);
                    }}
                  >
                    Sí, vaciar
                  </Btn>
                  <Btn onClick={() => setConfirm(false)}>Conservar boleto</Btn>
                </div>
              </div>
            )}
          </div>
          <aside className="min-w-0 order-first lg:order-last lg:sticky lg:top-[95px]">
            <Card className="match-stripe" titulo="El conjunto">
              {!actual && !fail ? (
                <Cargando alto={140} />
              ) : fail ? (
                <div role="alert">
                  <h2 className="text-base font-bold">
                    No pudimos calcular el boleto
                  </h2>
                  <p className="text-sm text-mut mt-2">
                    Tus selecciones siguen guardadas. Reintenta la conexión para
                    consultar el cálculo conjunto.
                  </p>
                  <Btn
                    onClick={() => setRevision((v) => v + 1)}
                    className="mt-4"
                  >
                    Reintentar cálculo
                  </Btn>
                </div>
              ) : rb ? (
                <>
                  {rb.disponible ? (
                    <>
                      <div
                        className="num text-5xl text-acc mt-3"
                        data-testid="probabilidad-conjunta"
                      >
                        {pct(rb.prob, 1)}
                      </div>
                      <p className="text-xs text-mut mt-2">
                        Probabilidad de que todas las selecciones acierten
                      </p>
                      <div className="grid grid-cols-2 gap-3 border-t border-line2 mt-5 pt-4">
                        <div>
                          <T>Cuota total</T>
                          <div className="num text-xl mt-2">
                            {num(rb.cuota)}
                          </div>
                        </div>
                        <div>
                          <T>Cuota justa</T>
                          <div className="num text-xl mt-2">
                            {num(rb.justa)}
                          </div>
                        </div>
                      </div>
                      <div className="mt-4">
                        <Kpi
                          items={[
                            {
                              label: "Valor esperado",
                              valor: signed(rb.ev),
                              cls: (rb.ev ?? 0) > 0 ? "text-ok" : "text-bad",
                            },
                            {
                              label: "EV mínimo",
                              valor: signed(rb.ev_lo),
                              sub: "sensibilidad heurística",
                            },
                          ]}
                        />
                      </div>
                      <details className="mt-3">
                        <summary className="min-h-11 flex items-center text-xs text-mut">
                          Escenarios y sensibilidad
                        </summary>
                        <p className="text-xs text-mut leading-relaxed">
                          Probabilidad {pct(rb.lo, 1)}–{pct(rb.hi, 1)} · EV
                          máximo {signed(rb.ev_hi)}. Son escenarios heurísticos,
                          sin cobertura estadística validada.
                        </p>
                      </details>
                    </>
                  ) : (
                    <div role="status" className="bg-card2 rounded-xl p-4">
                      <h3 className="font-bold text-base">
                        Cálculo conjunto no disponible
                      </h3>
                      <p className="text-sm text-mut mt-2">
                        El motor no puede asignar una probabilidad válida a esta
                        combinación.
                      </p>
                      <div className="text-xs text-mut mt-3">
                        Producto de cuotas introducidas: {num(rb.cuota)}
                      </div>
                    </div>
                  )}
                  <div className="space-y-3 mt-4">
                    {rb.advertencias.map((a, i) => (
                      <p
                        key={i}
                        className="text-xs leading-relaxed text-mut border-l-2 border-warn pl-3"
                      >
                        {a}
                      </p>
                    ))}
                  </div>
                  <Nota>
                    El motor trata las dependencias y devoluciones. La cuota
                    total no equivale a una probabilidad; ninguna estimación
                    garantiza un resultado.
                  </Nota>
                </>
              ) : null}
            </Card>
            <details className="disclosure">
              <summary>Banca y Kelly</summary>
              <div className="disclosure-body">
                <p className="text-xs text-mut leading-relaxed mb-4">
                  Kelly usa las liquidaciones y el mínimo de los escenarios de
                  sensibilidad. Es una referencia matemática, no una garantía de
                  rentabilidad.
                </p>
                <label className="block text-sm font-semibold">
                  Banca de referencia (Q)
                  <input
                    className="ctl mt-2"
                    type="number"
                    inputMode="decimal"
                    min="1"
                    step="50"
                    value={banca}
                    onChange={(e) =>
                      setBanca(Math.max(1, Number(e.target.value) || 1))
                    }
                  />
                </label>
                <p className="text-xs text-mut mt-2 mb-4">
                  Guardada localmente; no representa una cuenta ni un saldo
                  conectado.
                </p>
                {stk ? (
                  !stk.disponible ? (
                    <p className="text-xs leading-relaxed text-mut">
                      {stk.advertencia}
                    </p>
                  ) : stk.sin_valor ? (
                    <div className="text-sm font-semibold">
                      Sin valor en los escenarios de sensibilidad: Kelly no
                      asigna apuesta.
                    </div>
                  ) : (
                    <Kpi
                      items={stk.opciones.map((o) => ({
                        label: o.nombre,
                        valor: q(o.monto),
                        sub: pct(o.fraccion, 1),
                      }))}
                    />
                  )
                ) : (
                  <p className="text-xs text-mut">
                    Disponible después de un cálculo conjunto válido.
                  </p>
                )}
              </div>
            </details>
          </aside>
        </div>
      )}
    </>
  );
}

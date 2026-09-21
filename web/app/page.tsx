"use client";
// Inicio: resumen de la liga, boleto en curso, tabla, tendencias y medias por métrica.
import Link from "next/link";
import { useState } from "react";
import { METRICAS, METRICA_CORTA, type VistaInicio } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { useStore } from "@/lib/store";
import { diaMes, num, pct, resumenLocal, signed } from "@/lib/fmt";
import { Bar, Btn, Card, Cargando, ErrorBox, Nota, Pills, T, Trio } from "@/components/ui";
import { Crest, LigaLogo } from "@/components/Crest";
import { TablaPosiciones } from "@/components/Tabla";

export default function Inicio() {
  const { liga, boleto } = useStore();
  const [metT, setMetT] = useState("corners");
  const { data: v, error } = useApi<VistaInicio>(`/liga/${liga}`, { tendencias: metT });
  const rb = resumenLocal(boleto);

  if (error) return <ErrorBox error={error} />;
  if (!v) return <><Cargando alto={180} /><Cargando alto={260} /></>;
  const ult = diaMes(v.ultimo);
  const val = v.validacion;
  const media = v.tendencias.media_liga;
  const tope = Math.max(...v.tendencias.filas.map((f) => f.prom), media) * 1.1;

  return (
    <>
      <section className="hero rounded-card px-4 pt-4 pb-3 my-2.5">
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-white/90"><LigaLogo liga={liga} size={34} /></span>
          <div>
            <div className="text-[1.25rem] font-extrabold tracking-tight leading-tight">{v.nombre}</div>
            <div className="text-[0.78rem] text-mut font-semibold">Temporada {v.temporada}</div>
          </div>
        </div>
        <Trio items={[
          { valor: v.partidos_temporada, label: "partidos" },
          { valor: <>{ult.dia} <span className="text-[1.5rem]">{ult.mes}</span></>, label: "último dato" },
          { valor: v.equipos.length, label: "equipos" },
        ]} />
        <div className="text-[0.74rem] text-mut2 font-semibold">
          {val && <><span className={val.ok && !val.avisos?.length ? "text-ok" : "text-bad"}>datos {val.ok ? "validados ✓" : "con errores"}</span> · </>}
          {v.partidos_total} partidos cargados ({v.torneos_recientes.join(" y ")}) · se actualiza a diario a las 6:00 am
        </div>
      </section>

      <div className="grid grid-cols-2 gap-2">
        <Link href="/partido" className="contents"><Btn primary className="w-full">Armar parlay</Btn></Link>
        <Link href="/cara" className="contents"><Btn className="w-full">Cara a cara</Btn></Link>
      </div>

      {rb && (
        <Link href="/boleto" className="block">
          <Card titulo="Boleto en curso" right={<span className="text-[0.78rem] font-bold text-acc">ver →</span>}>
            <div className="flex justify-between items-center">
              <div>
                <T>{rb.n} pata{rb.n > 1 ? "s" : ""}</T>
                <div className="num text-[1.5rem] mt-1">cuota {num(rb.cuota)}</div>
                <div className="text-[0.74rem] text-mut mt-1">justa {num(1 / rb.prob)} · prob. {pct(rb.prob)}</div>
              </div>
              <div className="text-right">
                <T>EV</T>
                <div className={`num text-[2rem] mt-1 ${rb.ev > 0 ? "text-ok" : "text-bad"}`}>{signed(rb.ev)}</div>
                <div className="text-[0.74rem] text-mut mt-1">pesimista {signed(rb.ev_lo)} · optimista {signed(rb.ev_hi)}</div>
              </div>
            </div>
          </Card>
        </Link>
      )}

      <Card titulo="Tabla" desc={`Calculada con los partidos cargados de la temporada ${v.temporada}. Franja verde = Champions, ámbar = Europa, roja = descenso (orientativo).`}
        right={<Link href="/tabla" className="text-[0.78rem] font-bold text-acc">completa →</Link>} className="px-3!">
        <TablaPosiciones liga={liga} filas={v.tabla.slice(0, 6)} compacta />
      </Card>

      <Card titulo="Tendencias · últimos 5" desc="Promedio del equipo (a favor + en contra) en sus últimos 5 partidos, comparado con la media de la liga. Sirve para elegir qué partido y mercado analizar. Barra = promedio del equipo; marca vertical = media de la liga.">
        <Pills opciones={Object.keys(METRICAS)} valor={metT} onChange={setMetT} format={(m) => METRICA_CORTA[m]} small />
        <div className="flex justify-between mt-2 mb-1"><T>{METRICAS[v.tendencias.metrica]} por partido</T><T>media liga {num(media, 1)}</T></div>
        {v.tendencias.filas.map((f) => (
          <div key={f.equipo} className="border-t border-line2 first:border-t-0 py-2.5">
            <div className="flex items-center gap-2.5">
              <Crest liga={liga} equipo={f.equipo} size={30} />
              <div className="font-bold text-[0.95rem] flex-1 min-w-0 truncate">{f.equipo}</div>
              <div className="num text-[1.4rem]">{num(f.prom, 1)} <span className="text-[0.72rem] text-mut font-semibold tracking-normal">{signed(f.prom - media, 1)}</span></div>
            </div>
            <Bar valor={f.prom} marca={media} max={tope} color={f.prom >= media ? "var(--ok)" : "var(--mut2)"} alto={5} />
            <div className="text-[0.72rem] text-mut2">a favor {num(f.favor, 1)} · en contra {num(f.contra, 1)}</div>
          </div>
        ))}
      </Card>

      <Card titulo="Medias de la liga" desc="Promedio de todos los partidos cargados. Línea = la .5 más cercana a la media del total; Over = en qué porcentaje de partidos el total superó esa línea. Sirve para saber qué tan normal es un Over antes de mirar a los equipos.">
        <table className="st">
          <thead><tr><th></th><th>Local</th><th>Visit.</th><th>Total</th><th>Línea</th><th>Over</th></tr></thead>
          <tbody>
            {v.medias.map((m) => (
              <tr key={m.metrica}>
                <td className="font-semibold">{m.nombre}</td><td>{num(m.local, m.decimales)}</td><td>{num(m.visitante, m.decimales)}</td>
                <td className="font-extrabold">{num(m.total, m.decimales)}</td><td>{m.linea}</td><td className="font-extrabold">{pct(m.pct_over)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <Nota>Datos: football-data.co.uk (Europa) y ESPN (Liga MX).</Nota>
      </Card>
    </>
  );
}

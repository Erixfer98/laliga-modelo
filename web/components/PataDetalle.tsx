"use client";
// Detalle de una pata: historial por equipo (barras + estadísticas), partido a partido y "qué dice el modelo".
import type { Hist, Pata, Stats, VistaPartido } from "@/lib/api";
import { METRICAS } from "@/lib/api";
import { num, pct } from "@/lib/fmt";
import { Card, Nota } from "./ui";
import { Crest } from "./Crest";
import { BarrasPartidos, BarrasPoisson, Matriz } from "./charts";
import { Forma } from "./Tabla";

type Col = "a_favor" | "en_contra" | "total";
const esCol = (c: string): c is Col => c === "a_favor" || c === "en_contra" || c === "total";
const QUE: Record<string, string> = { a_favor: "a favor", en_contra: "en contra", total: "total" };

function TablaStats({ st, linea, over, refF, refC, refT }: { st: Stats; linea: number; over: boolean; refF: number; refC: number; refT: number }) {
  if (!st) return <div className="text-[0.8rem] text-mut">sin partidos con ese filtro</div>;
  const filas: [string, keyof NonNullable<Stats>["a_favor"]][] = [["Media", "media"], ["Mediana", "mediana"], ["Desv. est.", "desv"], ["Mín", "min"], ["Máx", "max"], [`% ${over ? "Over" : "Under"} ${linea}`, "pct"]];
  return (
    <table className="st">
      <thead><tr><th></th><th>A favor</th><th>En contra</th><th>Total</th></tr></thead>
      <tbody>
        {filas.map(([nm, k]) => {
          const f = (x: number) => (k === "pct" ? pct(x) : num(x, 1));
          return <tr key={k}><td>{nm}</td><td>{f(st.a_favor[k])}</td><td>{f(st.en_contra[k])}</td><td>{f(st.total[k])}</td></tr>;
        })}
        <tr className="liga"><td>Media liga</td><td>{num(refF, 1)}</td><td>{num(refC, 1)}</td><td>{num(refT, 1)}</td></tr>
      </tbody>
    </table>
  );
}

function Cabecera({ v, lado, right }: { v: VistaPartido; lado: "l" | "v"; right: React.ReactNode }) {
  const nombre = lado === "l" ? v.local : v.visitante;
  return (
    <div className="flex items-center gap-2.5 mb-2">
      <Crest liga={v.liga} equipo={nombre} size={34} lado={lado} />
      <div className="font-extrabold text-[1rem] flex-1 min-w-0 truncate">{nombre}</div>
      {right}
    </div>
  );
}

/** Tarjeta de un equipo: cuántas veces cumplió, barras partido a partido y estadísticas. */
export function HistorialEquipo({ v, p, lado }: { v: VistaPartido; p: Pata; lado: "l" | "v" }) {
  const ml = v.medias_liga, met = v.metrica;
  const h = lado === "l" ? p.historial_local : p.historial_visitante;
  const st = lado === "l" ? p.stats_local : p.stats_visitante;
  const serie = lado === "l" ? p.serie_l : p.serie_v;
  const hits = lado === "l" ? p.hl : p.hv;
  const col = lado === "l" ? p.col_l : p.col_v;
  const [refF, refC] = lado === "l" ? [ml.local, ml.visitante] : [ml.visitante, ml.local];
  const color = lado === "l" ? "var(--acc)" : "var(--vis)";
  const nombreMet = METRICAS[met].toLowerCase();
  let chart, sub;
  if (esCol(col)) {
    const refChart = col === "a_favor" ? refF : col === "en_contra" ? refC : ml.total;
    chart = <BarrasPartidos h={h} col={col} linea={p.linea} mediaLiga={refChart} ok={serie} color={color} />;
    sub = `${nombreMet} ${QUE[col]} por partido · barra de color = cumplió la pata`;
  } else {
    chart = <BarrasPartidos h={h} col="total" linea={ml.total} mediaLiga={ml.total} ok={h.map((g) => g.total > ml.total)} color={color} sinLinea />;
    sub = `${nombreMet} total por partido · barra de color = sobre la media de la liga`;
  }
  return (
    <Card>
      <Cabecera v={v} lado={lado} right={<div><span className="num text-[1.5rem]">{hits}/{h.length}</span> <span className="text-[0.78rem] text-mut font-semibold">cumplió</span></div>} />
      {chart}
      <div className="text-[0.72rem] text-mut2">{sub} · antiguo → reciente · C casa / F fuera</div>
      <div className="mt-3"><TablaStats st={st} linea={p.linea} over={p.over} refF={refF} refC={refC} refT={ml.total} /></div>
    </Card>
  );
}

/** Partido a partido estilo app: local - marcador - visitante, racha y el valor de la pata en cada partido. */
export function ListaPartidos({ v, p, lado }: { v: VistaPartido; p: Pata; lado: "l" | "v" }) {
  const equipo = lado === "l" ? v.local : v.visitante;
  const h: Hist[] = lado === "l" ? p.historial_local : p.historial_visitante;
  const serie = lado === "l" ? p.serie_l : p.serie_v;
  const col = lado === "l" ? p.col_l : p.col_v;
  if (!h.length) return <Card><Cabecera v={v} lado={lado} right={null} /><div className="text-[0.8rem] text-mut">sin partidos con ese filtro</div></Card>;
  const filas = h.map((g, i) => {
    const [gl, gv] = g.marcador.split("-").map(Number);
    const casa = g.condicion === "Casa";
    const [gf, gc] = casa ? [gl, gv] : [gv, gl];
    const res = gf > gc ? "g" : gf < gc ? "p" : "e";
    return { g, ok: serie[i], gl, gv, casa, res, home: casa ? equipo : g.rival, away: casa ? g.rival : equipo };
  });
  const cuenta = (r: string) => filas.filter((f) => f.res === r).length;
  const forma = filas.map((f) => f.res).reverse();
  const que = QUE[col] ?? "cumple";
  return (
    <Card>
      <Cabecera v={v} lado={lado} right={<div className="text-[0.8rem] text-mut font-semibold">{cuenta("g")}G {cuenta("e")}E {cuenta("p")}P</div>} />
      <div className="flex justify-between items-center mb-1.5">
        <Forma forma={forma} n={forma.length} />
        <div className="text-[0.78rem] text-mut">{METRICAS[v.metrica].toLowerCase()} {que} · <span className="text-txt font-bold">{serie.filter(Boolean).length}/{h.length}</span> cumplió</div>
      </div>
      {filas.map((f, i) => (
        <div key={i} className="flex items-center gap-1.5 py-2 border-b border-line2 last:border-b-0 text-[0.82rem]">
          <div className="w-[46px] shrink-0 text-[0.64rem] text-mut2 font-semibold leading-tight">{f.g.fecha}<br />{f.casa ? "Casa" : "Fuera"}</div>
          <div className={`flex-1 min-w-0 truncate text-right ${f.casa ? "font-extrabold" : "text-mut"}`}>{f.home}</div>
          <div className={`w-[48px] shrink-0 text-center font-extrabold rounded-lg py-1 text-white ${f.res === "g" ? "bg-ok" : f.res === "p" ? "bg-bad" : "bg-[#6b7280]"}`}>{f.gl}-{f.gv}</div>
          <div className={`flex-1 min-w-0 truncate ${f.casa ? "text-mut" : "font-extrabold"}`}>{f.away}</div>
          <div className={`w-[54px] shrink-0 text-right leading-tight ${f.ok ? "text-ok" : "text-mut2"}`}>
            {esCol(col) ? (
              <><b className="text-[1.05rem]">{f.g[col]}</b><div className="text-[0.62rem]">{col === "total" ? `${f.g.a_favor}·${f.g.en_contra}` : v.metrica === "goles" ? "" : QUE[col]}</div></>
            ) : <b className="text-[1.05rem]">{f.ok ? "✓" : "✗"}</b>}
          </div>
        </div>
      ))}
      <Nota>Racha: antiguo → reciente. Marcador verde = ganó, rojo = perdió, gris = empate. Valor en verde = en ese partido se cumplió la pata.</Nota>
    </Card>
  );
}

/** "Qué dice el modelo": matriz (goles), diferencia (mayor número) o distribución (resto). */
export function GraficoModelo({ v, p }: { v: VistaPartido; p: Pata }) {
  const g = p.grafico, et = METRICAS[v.metrica].toLowerCase();
  if (g.tipo === "matriz") return <Matriz g={g} local={v.local} visitante={v.visitante} />;
  if (g.tipo === "diferencia") return <BarrasPoisson valores={g.valores} signo nota={`Diferencia de ${et}: ${v.local} menos ${v.visitante}, según Poisson. Positivo = más el local, negativo = más el visitante. Verde = gana la pata.`} />;
  return <BarrasPoisson valores={g.valores} nota={`Probabilidad de cada cantidad de ${et}${p.grupo === "Total" ? " total" : " " + p.grupo} según Poisson. Verde = cantidades con las que gana la pata.`} />;
}

export function Chip({ estado, ratio, n_ef, condicion }: { estado: string; ratio: number; n_ef: number; condicion: string }) {
  const color: Record<string, string> = { estable: "bg-ok", normal: "bg-warn", "volátil": "bg-bad", "pocos datos": "bg-mut2" };
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap" title={`${estado} · ${Math.round(n_ef)} partidos efectivos ${condicion}`}>
      <span className={`inline-block w-2 h-2 rounded-full ${color[estado] ?? "bg-mut2"}`} />{num(ratio, 1)}×
    </span>
  );
}

"use client";
// Cara a cara: enfrentamientos directos en el torneo vigente y el anterior, con la ficha de cada partido (9 métricas).
import { useState } from "react";
import { METRICA_CORTA, type VistaCara } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { useStore } from "@/lib/store";
import { corto, fechaLarga } from "@/lib/fmt";
import { Card, Cargando, ErrorBox, Toggle, Trio } from "@/components/ui";
import { Crest } from "@/components/Crest";
import { CabeceraPartido, usePartido } from "@/components/Selectores";

export default function Cara() {
  const { liga } = useStore();
  const { local, visitante, listo } = usePartido();
  const [soloCasa, setSoloCasa] = useState(false);
  const { data: v, error } = useApi<VistaCara>(listo ? `/liga/${liga}/cara` : null, { local, visitante, solo_casa: soloCasa });

  if (error) return <><CabeceraPartido /><ErrorBox error={error} /></>;
  const torneos = v?.torneos.join(" y ") ?? "";
  return (
    <>
      <CabeceraPartido sub="cara a cara" />
      <div className="px-1"><Toggle label={`Solo con ${local} en casa`} valor={soloCasa} onChange={setSoloCasa} /></div>
      {!v || v.local !== local || v.visitante !== visitante ? <Cargando alto={160} /> : (
        <>
          <Card titulo="Récord directo" desc={`Solo ${torneos}${soloCasa ? `, con ${local} en casa` : ""}. Son pocos partidos: sirven como contexto, no como prueba.`}>
            {v.n === 0 ? (
              <div className="text-[0.84rem] text-mut">{local} y {visitante} no se han cruzado en {torneos}{soloCasa ? " con el local en casa" : ""}.</div>
            ) : (
              <>
                <Trio items={[
                  { valor: v.G, label: corto(local, 14), color: "var(--acc)" },
                  { valor: v.E, label: `empate${v.E !== 1 ? "s" : ""}`, color: "#8a93a6" },
                  { valor: v.P, label: corto(visitante, 14), color: "var(--vis)" },
                ]} />
                <div className="flex h-2.5 rounded-full overflow-hidden bg-barbg">
                  <div style={{ width: `${(v.G / v.n) * 100}%`, background: "var(--acc)" }} />
                  <div style={{ width: `${(v.E / v.n) * 100}%`, background: "#8a93a6" }} />
                  <div style={{ width: `${(v.P / v.n) * 100}%`, background: "var(--vis)" }} />
                </div>
                <div className="text-[0.76rem] text-mut2 mt-2">{v.n} partido{v.n !== 1 ? "s" : ""} en {torneos}</div>
              </>
            )}
          </Card>

          {v.partidos.map((g, i) => {
            const cHome = g.local === local ? "var(--acc)" : "var(--vis)", cAway = g.local === local ? "var(--vis)" : "var(--acc)";
            const ladoHome = g.local === local ? "l" : "v", ladoAway = g.local === local ? "v" : "l";
            return (
              <Card key={i} className="px-3!">
                <div className="text-[0.72rem] font-bold text-mut2 uppercase tracking-[0.06em] text-center">{g.temporada} · {fechaLarga(g.fecha)}</div>
                <div className="flex items-center justify-between gap-2 my-3">
                  <div className="flex-1 flex flex-col items-center gap-1.5 min-w-0"><Crest liga={liga} equipo={g.local} size={44} lado={ladoHome} /><span className="text-[0.8rem] font-bold text-center truncate w-full">{g.local}</span></div>
                  <div className="num text-[2.2rem] px-2 whitespace-nowrap">{g.goles_local ?? "?"} <span className="text-mut2 text-[1.4rem]">–</span> {g.goles_visitante ?? "?"}</div>
                  <div className="flex-1 flex flex-col items-center gap-1.5 min-w-0"><Crest liga={liga} equipo={g.visitante} size={44} lado={ladoAway} /><span className="text-[0.8rem] font-bold text-center truncate w-full">{g.visitante}</span></div>
                </div>
                {Object.entries(g.metricas).map(([met, m]) => m.local === null || m.visitante === null ? null : (
                  <div key={met} className="flex items-center justify-between gap-2 py-1.5 border-b border-line2 last:border-b-0 text-[0.86rem]">
                    <span className="min-w-[38px] text-center px-2 py-0.5 rounded-full font-extrabold" style={m.local > m.visitante ? { background: cHome, color: "#fff" } : {}}>{m.local}</span>
                    <span className="flex-1 text-center text-mut text-[0.78rem] font-semibold">{METRICA_CORTA[met]}</span>
                    <span className="min-w-[38px] text-center px-2 py-0.5 rounded-full font-extrabold" style={m.visitante > m.local ? { background: cAway, color: "#fff" } : {}}>{m.visitante}</span>
                  </div>
                ))}
              </Card>
            );
          })}
        </>
      )}
    </>
  );
}

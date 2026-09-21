"use client";
// Boleto: las patas que llevas, tu banca y el stake sugerido (Kelly con la probabilidad pesimista).
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiPost, type ResumenBoleto, type Stake } from "@/lib/api";
import { useStore } from "@/lib/store";
import { justa, num, pct, q, signed } from "@/lib/fmt";
import { Btn, Card, Kpi, Nota, T, Tag } from "@/components/ui";

export default function Boleto() {
  const { boleto, removeLeg, vaciar, banca, setBanca, listo } = useStore();
  const [res, setRes] = useState<{ resumen: ResumenBoleto; stake: Stake } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!listo) return;
    if (!boleto.length) { setRes(null); return; }
    let vivo = true;
    apiPost<{ resumen: ResumenBoleto; stake: Stake }>("/boleto", { patas: boleto, banca })
      .then((r) => { if (vivo) { setRes(r); setError(""); } })
      .catch((e: Error) => { if (vivo) setError(e.message); });
    return () => { vivo = false; };
  }, [boleto, banca, listo]);

  if (!listo) return null;
  if (!boleto.length) {
    return (
      <section className="hero rounded-card px-5 py-8 my-2.5 text-center">
        <div className="num text-[2rem]">Boleto vacío</div>
        <div className="text-[0.86rem] text-mut mt-2">Elige un mercado en Partido, escribe la cuota de la casa y agrégalo.</div>
        <Link href="/partido" className="contents"><Btn primary className="mt-5 w-full">Ir a Partido</Btn></Link>
      </section>
    );
  }
  const rb = res?.resumen, stk = res?.stake;

  return (
    <>
      <section className="hero rounded-card px-4 pt-4 pb-4 my-2.5">
        <div className="flex justify-between items-start">
          <div>
            <T>Boleto · {boleto.length} pata{boleto.length > 1 ? "s" : ""}</T>
            <div className="num text-[2.6rem] mt-1">{rb ? num(rb.cuota) : "…"}</div>
            <div className="text-[0.76rem] text-mut mt-1">cuota total · justa {rb ? num(rb.justa) : "…"} · prob. {rb ? pct(rb.prob) : "…"}</div>
          </div>
          <div className="text-right">
            <T>EV</T>
            <div className={`num text-[2.6rem] mt-1 ${rb && rb.ev > 0 ? "text-ok" : "text-bad"}`}>{rb ? signed(rb.ev) : "…"}</div>
            <div className="text-[0.76rem] text-mut mt-1">pesimista {rb ? signed(rb.ev_lo) : "…"} · optimista {rb ? signed(rb.ev_hi) : "…"}</div>
          </div>
        </div>
        {rb?.mismo_partido && <Nota>Patas del mismo partido no son independientes; la probabilidad combinada real difiere.</Nota>}
      </section>

      <Card titulo="Cuánto apostar" desc="Kelly calculado con la probabilidad pesimista del boleto: si con esa todavía hay valor, la apuesta aguanta un modelo demasiado optimista. Para parlays usa ¼ o ⅛ de Kelly.">
        <label className="block mb-3"><T>Banca (Q)</T>
          <input className="ctl mt-1 text-[1.1rem] font-extrabold" type="number" inputMode="numeric" min="1" step="50" value={banca} onChange={(e) => setBanca(Math.max(1, Number(e.target.value) || 1))} /></label>
        {error && <div className="text-bad text-[0.82rem]">{error}</div>}
        {stk && (stk.sin_valor
          ? <div className="rounded-2xl bg-card2 px-4 py-3"><T>Con la probabilidad pesimista ({rb ? pct(rb.lo) : ""})</T><div className="font-extrabold text-bad mt-1">Sin valor: Kelly dice no apostar</div></div>
          : <Kpi items={stk.opciones.map((o) => ({ label: o.nombre, valor: q(o.monto), sub: pct(o.fraccion, 1) }))} />)}
      </Card>

      <Card titulo="Patas" right={<button type="button" onClick={vaciar} className="text-[0.78rem] font-bold text-bad">vaciar</button>} className="px-3!">
        {boleto.map((l, i) => (
          <div key={i} className="flex items-center gap-2 px-2 py-3 mb-1.5 rounded-2xl bg-card2/50">
            <div className="flex-1 min-w-0">
              <div className="font-extrabold text-[0.98rem] leading-tight">{l.mercado}</div>
              <div className="text-[0.76rem] text-mut mt-0.5">{l.partido} · {l.metrica}</div>
              <div className="text-[0.76rem] text-mut2 mt-0.5">modelo {pct(l.prob)} ({pct(l.lo)}–{pct(l.hi)}) · justa {justa(l.prob)}</div>
            </div>
            <div className="text-right shrink-0">
              <div className="num text-[1.3rem]">{num(l.cuota)}</div>
              <div className="mt-1"><Tag cls={l.cls}>{l.cal}</Tag></div>
            </div>
            <button type="button" onClick={() => removeLeg(i)} className="w-9 h-9 rounded-xl bg-card text-mut hover:text-bad shrink-0" aria-label="Quitar pata">✕</button>
          </div>
        ))}
        <Link href="/partido" className="contents"><Btn className="w-full mt-1">+ Agregar pata</Btn></Link>
      </Card>
    </>
  );
}

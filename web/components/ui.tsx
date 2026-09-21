"use client";
// Piezas visuales básicas. Todas usan los colores de globals.css (bg-card, text-mut, ...): cambia la paleta y cambian todas.
import { useState, type ReactNode } from "react";

/** Botón ⓘ que muestra u oculta una explicación corta. */
export function Info({ desc }: { desc: string }) {
  const [abierto, setAbierto] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setAbierto(!abierto)} aria-label="Qué es esto"
        className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-[0.72rem] font-bold shrink-0 transition-colors ${abierto ? "bg-acc text-white" : "bg-card2 text-mut hover:text-txt"}`}>i</button>
      {abierto && <div className="basis-full text-[0.82rem] leading-[1.5] text-mut mt-1">{desc}</div>}
    </>
  );
}

/** Tarjeta. Con `titulo` dibuja el encabezado adentro (título + ⓘ con la explicación + algo a la derecha), estilo app. */
export function Card({ titulo, desc, right, children, flat, hero, className = "" }: {
  titulo?: ReactNode; desc?: string; right?: ReactNode; children: ReactNode; flat?: boolean; hero?: "hero" | "hero-ok"; className?: string;
}) {
  return (
    <section className={`rounded-card px-4 py-4 my-2.5 ${hero ?? (flat ? "bg-card2" : "bg-card")} ${className}`}>
      {titulo && (
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <h3 className="text-[1rem] font-extrabold tracking-tight">{titulo}</h3>
          {desc && <Info desc={desc} />}
          {right && <div className="ml-auto">{right}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

/** Título de bloque fuera de tarjeta (poco uso: agrupar varias tarjetas). */
export function Sec({ titulo, desc, right }: { titulo: string; desc?: string; right?: ReactNode }) {
  return (
    <div className="mt-5 mb-1 flex flex-wrap items-center gap-2 px-1">
      <div className="text-[1.15rem] font-extrabold tracking-tight">{titulo}</div>
      {desc && <Info desc={desc} />}
      {right && <div className="ml-auto">{right}</div>}
    </div>
  );
}

/** Nota al pie dentro de una tarjeta (cómo leerla). */
export function Nota({ children }: { children: ReactNode }) {
  return <div className="text-[0.78rem] leading-[1.45] text-mut2 border-t border-line2 mt-3 pt-2.5">{children}</div>;
}

export function T({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`text-[0.7rem] text-mut2 font-bold uppercase tracking-[0.06em] leading-[1.3] ${className}`}>{children}</div>;
}

export function Tag({ cls, children }: { cls: string; children: ReactNode }) {
  return <span className={`tag ${cls}`}>{children}</span>;
}

/** Barra horizontal: relleno = valor; marca vertical = referencia. */
export function Bar({ valor, marca, max, color, alto = 6 }: { valor: number; marca: number; max: number; color: string; alto?: number }) {
  const p = max ? Math.min(valor / max, 1) * 100 : 0;
  const m = max ? Math.min(marca / max, 1) * 100 : 0;
  return (
    <div className="relative rounded-full bg-barbg my-2" style={{ height: alto }}>
      <div className="rounded-full" style={{ width: `${p}%`, background: color, height: alto }} />
      <div className="absolute w-0.5 bg-mark opacity-90 rounded" style={{ left: `${m}%`, top: -3, height: alto + 6 }} />
    </div>
  );
}

/** Fila de opciones tipo chips (una sola elegida). */
export function Pills<T extends string | number>({ opciones, valor, onChange, format, small, className = "" }: {
  opciones: T[]; valor: T; onChange: (v: T) => void; format?: (v: T) => string; small?: boolean; className?: string;
}) {
  return (
    <div className={`scrollx flex gap-1.5 py-1 -mx-1 px-1 ${className}`}>
      {opciones.map((o) => (
        <button key={String(o)} type="button" onClick={() => onChange(o)}
          className={`shrink-0 rounded-full font-bold transition-colors ${small ? "px-3 py-1.5 text-[0.78rem]" : "px-4 py-2 text-[0.84rem]"}
            ${o === valor ? "bg-txt text-bg" : "bg-card2 text-mut hover:text-txt"}`}>
          {format ? format(o) : String(o)}
        </button>
      ))}
    </div>
  );
}

export function Btn({ children, onClick, primary, className = "", disabled }: {
  children: ReactNode; onClick?: () => void; primary?: boolean; className?: string; disabled?: boolean;
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled}
      className={`rounded-2xl px-4 min-h-[46px] font-bold text-[0.92rem] transition-all active:scale-[0.98] disabled:opacity-50
        ${primary ? "bg-acc text-white hover:brightness-110" : "bg-card2 text-txt hover:bg-line"} ${className}`}>
      {children}
    </button>
  );
}

export function Toggle({ label, valor, onChange }: { label: string; valor: boolean; onChange: (v: boolean) => void }) {
  return (
    <button type="button" onClick={() => onChange(!valor)} className="flex items-center gap-2 text-[0.84rem] font-semibold text-mut min-h-[44px]">
      <span className={`relative inline-block w-10 h-6 rounded-full transition-colors ${valor ? "bg-acc" : "bg-barbg"}`}>
        <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-all ${valor ? "left-[18px]" : "left-0.5"}`} />
      </span>
      <span className={valor ? "text-txt" : ""}>{label}</span>
    </button>
  );
}

/** Dos o tres números grandes en fila (veredicto, récord, resumen). */
export function Trio({ items }: { items: { valor: ReactNode; label: ReactNode; sub?: ReactNode; color?: string }[] }) {
  return (
    <div className="flex my-3">
      {items.map((it, i) => (
        <div key={i} className={`flex-1 text-center px-1 ${i ? "border-l border-line2" : ""}`}>
          <div className="num text-[2.3rem] whitespace-nowrap" style={{ color: it.color }}>{it.valor}</div>
          <T className="mt-1.5">{it.label}</T>
          {it.sub && <div className="text-[0.74rem] text-mut mt-0.5">{it.sub}</div>}
        </div>
      ))}
    </div>
  );
}

/** Cuadrícula de indicadores pequeños (escenarios, EV, Kelly). */
export function Kpi({ items, flat }: { items: { label: ReactNode; valor: ReactNode; sub?: ReactNode; cls?: string }[]; flat?: boolean }) {
  return (
    <div className="flex gap-2">
      {items.map((it, i) => (
        <div key={i} className={`flex-1 rounded-2xl px-1 py-2.5 text-center ${flat ? "bg-card" : "bg-card2"}`}>
          <T>{it.label}</T>
          <div className={`num text-[1.5rem] mt-1 ${it.cls ?? ""}`}>{it.valor}</div>
          {it.sub && <div className="text-[0.72rem] text-mut mt-1 whitespace-nowrap">{it.sub}</div>}
        </div>
      ))}
    </div>
  );
}

export function Cargando({ alto = 120 }: { alto?: number }) {
  return <div className="rounded-card bg-card my-2.5 animate-pulse" style={{ height: alto }} />;
}

export function ErrorBox({ error }: { error: string }) {
  return (
    <Card titulo="No pude hablar con la API">
      <div className="text-[0.82rem] text-mut break-words">{error}</div>
      <div className="text-[0.82rem] text-mut mt-2">¿Está corriendo? En la carpeta del proyecto: <code className="text-txt">uvicorn api:app --reload</code></div>
    </Card>
  );
}

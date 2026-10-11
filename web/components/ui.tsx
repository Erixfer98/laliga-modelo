"use client";
import { useId, useState, type ReactNode } from "react";
export function Info({ desc }: { desc: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <>
      <button
        type="button"
        aria-label="Más información"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(!open)}
        className="inline-flex items-center justify-center min-w-11 min-h-11 text-mut rounded-lg text-sm"
      >
        ⓘ
      </button>
      {open && (
        <div
          id={id}
          className="basis-full text-sm leading-relaxed text-mut pb-2"
        >
          {desc}
        </div>
      )}
    </>
  );
}
export function Card({
  titulo,
  desc,
  right,
  children,
  flat,
  className = "",
}: {
  titulo?: ReactNode;
  desc?: string;
  right?: ReactNode;
  children: ReactNode;
  flat?: boolean;
  hero?: "hero" | "hero-ok";
  className?: string;
}) {
  return (
    <section
      className={`rounded-card border border-line2 ${flat ? "bg-card2" : "bg-card"} p-4 md:p-5 mb-4 ${className}`}
    >
      {titulo && (
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <h2 className="text-base font-bold tracking-tight">{titulo}</h2>
          {desc && <Info desc={desc} />}{" "}
          {right && <div className="ml-auto">{right}</div>}
        </div>
      )}
      {children}
    </section>
  );
}
export function Sec({
  titulo,
  desc,
  right,
}: {
  titulo: string;
  desc?: string;
  right?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 mt-6 mb-3">
      <h2 className="text-lg font-bold tracking-tight">{titulo}</h2>
      {desc && <Info desc={desc} />}
      <div className="ml-auto">{right}</div>
    </div>
  );
}
export function Nota({ children }: { children: ReactNode }) {
  return (
    <div className="text-xs leading-relaxed text-mut border-t border-line2 mt-3 pt-3">
      {children}
    </div>
  );
}
export function T({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`eyebrow ${className}`}>{children}</div>;
}
export function Tag({ cls, children }: { cls: string; children: ReactNode }) {
  return <span className={`tag ${cls}`}>{children}</span>;
}
export function Bar({
  valor,
  marca,
  max,
  color,
  alto = 6,
}: {
  valor: number;
  marca: number;
  max: number;
  color: string;
  alto?: number;
}) {
  return (
    <div
      aria-hidden="true"
      className="relative rounded bg-barbg my-2"
      style={{ height: alto }}
    >
      <div
        className="rounded"
        style={{
          width: `${max ? Math.min(valor / max, 1) * 100 : 0}%`,
          background: color,
          height: alto,
        }}
      />
      <div
        className="absolute w-0.5 bg-mark"
        style={{
          left: `${max ? Math.min(marca / max, 1) * 100 : 0}%`,
          top: -2,
          height: alto + 4,
        }}
      />
    </div>
  );
}
export function Pills<T extends string | number>({
  opciones,
  valor,
  onChange,
  format,
  small,
  className = "",
  label = "Opciones",
}: {
  opciones: T[];
  valor: T;
  onChange: (v: T) => void;
  format?: (v: T) => string;
  small?: boolean;
  className?: string;
  label?: string;
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className={`scrollx flex gap-1 p-1 bg-card2 rounded-xl ${className}`}
    >
      {opciones.map((o) => (
        <button
          key={String(o)}
          type="button"
          aria-pressed={o === valor}
          onClick={() => onChange(o)}
          className={`shrink-0 min-h-11 rounded-lg px-3 ${small ? "text-xs" : "text-sm"} font-semibold ${o === valor ? "bg-card text-txt shadow-sm" : "text-mut hover:text-txt"}`}
        >
          {format ? format(o) : String(o)}
        </button>
      ))}
    </div>
  );
}
export function Btn({
  children,
  onClick,
  primary,
  className = "",
  disabled,
}: {
  children: ReactNode;
  onClick?: () => void;
  primary?: boolean;
  className?: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`min-h-12 rounded-xl px-5 text-sm font-bold transition-colors disabled:opacity-50 ${primary ? "primary" : "bg-card2 text-txt border border-line2"} ${className}`}
    >
      {children}
    </button>
  );
}
export function Toggle({
  label,
  valor,
  onChange,
}: {
  label: string;
  valor: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={valor}
      onClick={() => onChange(!valor)}
      className="flex gap-2 items-center min-h-11 text-sm text-mut"
    >
      <span
        aria-hidden="true"
        className={`relative w-9 h-5 rounded-full ${valor ? "bg-acc" : "bg-line"}`}
      >
        <span
          className={`absolute top-0.5 w-4 h-4 bg-card rounded-full ${valor ? "right-0.5" : "left-0.5"}`}
        />
      </span>
      {label}
    </button>
  );
}
export function Trio({
  items,
}: {
  items: {
    valor: ReactNode;
    label: ReactNode;
    sub?: ReactNode;
    color?: string;
  }[];
}) {
  return (
    <div className="flex my-4">
      {items.map((it, i) => (
        <div
          key={i}
          className={`flex-1 min-w-0 px-2 ${i ? "border-l border-line2" : ""}`}
        >
          <div className="num text-2xl md:text-3xl" style={{ color: it.color }}>
            {it.valor}
          </div>
          <div className="text-xs text-mut mt-2">{it.label}</div>
          {it.sub && <div className="text-xs text-mut mt-1">{it.sub}</div>}
        </div>
      ))}
    </div>
  );
}
export function Kpi({
  items,
  flat,
}: {
  items: {
    label: ReactNode;
    valor: ReactNode;
    sub?: ReactNode;
    cls?: string;
  }[];
  flat?: boolean;
}) {
  return (
    <div className="grid grid-cols-1 min-[360px]:grid-cols-2 sm:grid-cols-3 gap-2">
      {items.map((it, i) => (
        <div
          key={i}
          className={`rounded-xl p-3 ${flat ? "bg-card" : "bg-card2"}`}
        >
          <T>{it.label}</T>
          <div className={`num text-xl mt-2 ${it.cls ?? ""}`}>{it.valor}</div>
          {it.sub && <div className="text-xs text-mut mt-1">{it.sub}</div>}
        </div>
      ))}
    </div>
  );
}
export function Cargando({ alto = 120 }: { alto?: number }) {
  return (
    <div
      role="status"
      aria-label="Cargando datos"
      className="rounded-card bg-card2 my-4 animate-pulse"
      style={{ height: alto }}
    >
      <span className="sr-only">Cargando datos…</span>
    </div>
  );
}
export function ErrorBox({
  error,
  reintentar,
}: {
  error: string;
  reintentar?: () => void;
}) {
  return (
    <Card>
      <div role="alert">
        <h2 className="text-lg font-bold">No pudimos cargar los datos</h2>
        <p className="text-sm text-mut mt-2">
          {error.includes("409")
            ? "Los datos o el modelo cambiaron. Actualiza el análisis antes de añadir al boleto."
            : error.includes("422")
              ? "No se puede analizar esta selección con los datos disponibles. Revisa el enfrentamiento o los filtros."
              : "La conexión no está disponible en este momento. Tus selecciones siguen guardadas en este dispositivo."}
        </p>
      </div>
      <Btn
        onClick={reintentar ?? (() => window.location.reload())}
        className="mt-4"
      >
        Reintentar
      </Btn>
    </Card>
  );
}
export function Liquidacion({
  prob,
  push,
  loss,
}: {
  prob: number;
  push: number;
  loss: number;
}) {
  return (
    <div>
      <div className="prob-track" aria-hidden="true">
        <span className="prob-win" style={{ width: `${prob * 100}%` }} />
        <span className="prob-push" style={{ width: `${push * 100}%` }} />
        <span className="prob-loss" style={{ width: `${loss * 100}%` }} />
      </div>
      <dl className="grid grid-cols-3 mt-3 gap-2 text-xs">
        <div>
          <dt className="text-mut">Acierto</dt>
          <dd className="font-bold mt-1">{(prob * 100).toFixed(1)}%</dd>
        </div>
        <div>
          <dt className="text-mut">Devolución</dt>
          <dd className="font-bold mt-1">{(push * 100).toFixed(1)}%</dd>
        </div>
        <div>
          <dt className="text-mut">Fallo</dt>
          <dd className="font-bold mt-1">{(loss * 100).toFixed(1)}%</dd>
        </div>
      </dl>
    </div>
  );
}

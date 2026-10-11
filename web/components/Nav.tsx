"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { LIGAS } from "@/lib/api";
import { useStore } from "@/lib/store";
import { LigaLogo } from "./Crest";
import { Logo } from "./Logo";

const PATHS = {
  home: "M3 10 12 3l9 7v10h-6v-6H9v6H3z",
  ball: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 4 3.5 2.6-1.3 4.2H9.8L8.5 9.6Z",
  ticket: "M3 7h18v4a2 2 0 0 0 0 4v4H3v-4a2 2 0 0 0 0-4Zm7 0v12",
  more: "M4 6h16M4 12h16M4 18h16",
};
export function Icono({ d, size = 22 }: { d: string; size?: number }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={d} />
    </svg>
  );
}
const LINKS = [
  { href: "/", nombre: "Inicio", icono: PATHS.home },
  { href: "/partido", nombre: "Analizar", icono: PATHS.ball },
  { href: "/boleto", nombre: "Boleto", icono: PATHS.ticket },
];

function Apariencia() {
  const [theme, setTheme] = useState("system");
  useEffect(() => {
    const sync = () => {
      try {
        const t = localStorage.getItem("kuota-theme");
        setTheme(t === "light" || t === "dark" ? t : "system");
      } catch {}
    };
    sync();
    window.addEventListener("storage", sync);
    window.addEventListener("kuota-theme-change", sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener("kuota-theme-change", sync);
    };
  }, []);
  return (
    <label className="flex items-center gap-3 text-sm font-semibold">
      <span>Apariencia</span>
      <select
        aria-label="Apariencia"
        className="ctl ml-auto max-w-[150px]"
        value={theme}
        onChange={(e) => {
          const t = e.target.value;
          setTheme(t);
          if (t === "system") delete document.documentElement.dataset.theme;
          else document.documentElement.dataset.theme = t;
          try {
            localStorage.setItem("kuota-theme", t);
            window.dispatchEvent(new Event("kuota-theme-change"));
          } catch {}
        }}
      >
        <option value="system">Sistema</option>
        <option value="light">Claro</option>
        <option value="dark">Oscuro</option>
      </select>
    </label>
  );
}
export function Header({ conClave }: { conClave?: boolean }) {
  const path = usePathname();
  const { liga, setLiga, boleto } = useStore();
  return (
    <header className="sticky top-0 z-40 bg-card border-b border-line2">
      <div className="max-w-[1200px] mx-auto px-4 lg:px-6 h-[72px] flex items-center gap-8">
        <Link href="/" aria-label="Kuota, inicio" className="shrink-0">
          <Logo tam="1.8rem" />
        </Link>
        <nav
          aria-label="Navegación principal"
          className="hidden lg:flex items-center h-full gap-6 text-sm font-bold"
        >
          {[
            ...LINKS,
            { href: "/tabla", nombre: "Tabla" },
            { href: "/cara", nombre: "Cara a cara" },
            { href: "/diccionario", nombre: "Cómo funciona" },
          ].map((p) => (
            <Link
              key={p.href}
              href={p.href}
              aria-current={path === p.href ? "page" : undefined}
              className={`flex items-center h-full border-b-2 ${path === p.href ? "border-acc text-txt" : "border-transparent text-mut hover:text-txt"}`}
            >
              {p.nombre}
              {p.href === "/boleto" && boleto.length > 0 && (
                <span className="ml-2 rounded bg-card2 px-1.5 text-xs">
                  {boleto.length}
                </span>
              )}
            </Link>
          ))}
        </nav>
        <details className="relative ml-auto">
          <summary
            className="list-none min-h-11 flex items-center text-mut font-semibold text-xs cursor-pointer"
            aria-label="Preferencias"
          >
            Preferencias{" "}
            <span aria-hidden="true" className="ml-2">
              ⌄
            </span>
          </summary>
          <div className="absolute right-0 top-full w-[260px] rounded-card border border-line bg-card p-4 shadow-lg">
            <Apariencia />
            {conClave && (
              <form method="POST" action="/api/salir" className="mt-3">
                <button className="min-h-11 text-sm text-mut font-semibold w-full text-left">
                  Cerrar sesión
                </button>
              </form>
            )}
          </div>
        </details>
      </div>
      {["/", "/partido", "/cara", "/tabla"].includes(path) && (
        <div className="border-t border-line2">
          <div
            role="group"
            aria-label="Elegir liga"
            className="max-w-[1200px] mx-auto px-4 lg:px-6 flex gap-5 scrollx"
          >
            {Object.entries(LIGAS).map(([k, name]) => (
              <button
                key={k}
                aria-label={name}
                aria-pressed={liga === k}
                onClick={() => setLiga(k)}
                className={`flex items-center gap-2 shrink-0 min-h-[52px] text-xs font-bold border-b-2 ${liga === k ? "border-acc text-txt" : "border-transparent text-mut"}`}
              >
                <LigaLogo liga={k} size={24} />
                {name}
              </button>
            ))}
          </div>
        </div>
      )}
    </header>
  );
}
export function BarraInferior() {
  const path = usePathname();
  const { boleto } = useStore();
  const dialog = useRef<HTMLDialogElement>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (open) dialog.current?.showModal();
    else if (dialog.current?.open) dialog.current.close();
  }, [open]);
  useEffect(() => {
    setOpen(false);
  }, [path]);
  return (
    <>
      <nav
        aria-label="Navegación móvil"
        className="lg:hidden fixed bottom-0 inset-x-0 z-40 bg-card border-t border-line2 safe-b"
      >
        <div className="grid grid-cols-4 max-w-xl mx-auto">
          {LINKS.map((p) => (
            <Link
              key={p.href}
              href={p.href}
              aria-current={path === p.href ? "page" : undefined}
              className={`relative flex flex-col items-center gap-1 py-3 min-h-[64px] text-[.7rem] font-bold ${path === p.href ? "text-acc" : "text-mut"}`}
            >
              <Icono d={p.icono} />
              {p.nombre}
              {p.href === "/boleto" && boleto.length > 0 && (
                <span className="absolute top-1 right-[26%] primary text-[10px] px-1.5 rounded-full">
                  {boleto.length}
                </span>
              )}
            </Link>
          ))}
          <button
            onClick={() => setOpen(true)}
            aria-haspopup="dialog"
            className={`flex flex-col items-center gap-1 py-3 text-[.7rem] font-bold ${["/tabla", "/cara", "/diccionario"].includes(path) ? "text-acc" : "text-mut"}`}
          >
            <Icono d={PATHS.more} />
            Más
          </button>
        </div>
      </nav>
      <dialog
        ref={dialog}
        onClose={() => setOpen(false)}
        onClick={(e) => {
          if (e.target === dialog.current) setOpen(false);
        }}
        aria-labelledby="mas-title"
        className="m-auto w-[calc(100%_-_32px)] max-w-sm bg-card text-txt p-5 rounded-card border border-line backdrop:bg-black/40"
      >
        <div className="flex items-center justify-between mb-3">
          <h2 id="mas-title" className="text-xl font-bold">
            Explora Kuota
          </h2>
          <button
            aria-label="Cerrar menú"
            onClick={() => setOpen(false)}
            className="w-11 h-11 rounded-lg bg-card2"
          >
            ✕
          </button>
        </div>
        {[
          { href: "/tabla", name: "Tabla de posiciones" },
          { href: "/cara", name: "Cara a cara" },
          { href: "/diccionario", name: "Cómo funciona y glosario" },
        ].map((l) => (
          <Link
            key={l.href}
            href={l.href}
            onClick={() => setOpen(false)}
            className="flex items-center justify-between min-h-14 border-b border-line2 font-semibold"
          >
            {l.name}
            <span aria-hidden="true">→</span>
          </Link>
        ))}
        <div className="mt-4">
          <Apariencia />
        </div>
      </dialog>
    </>
  );
}

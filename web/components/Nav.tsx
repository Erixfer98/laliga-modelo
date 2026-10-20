"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { LIGAS } from "@/lib/api";
import { useStore } from "@/lib/store";
import { LigaLogo } from "./Crest";
import { Logo } from "./Logo";

const PATHS = {
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
  { href: "/", nombre: "Partido", icono: PATHS.ball },
  { href: "/boleto", nombre: "Boleto", icono: PATHS.ticket },
  { href: "/mas", nombre: "Más", icono: PATHS.more },
];
const EN_MAS = ["/mas", "/liga", "/tabla", "/cara", "/diccionario"];
const activo = (href: string, path: string) =>
  href === "/mas" ? EN_MAS.includes(path) : path === href;
export function Apariencia() {
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
export function Header() {
  const path = usePathname();
  const { liga, setLiga, boleto } = useStore();
  return (
    <header className="sticky top-0 z-40 bg-card border-b border-line2">
      <div className="max-w-[1200px] mx-auto px-4 lg:px-6 h-14 flex items-center gap-8">
        <Link href="/" aria-label="Kuota, partido" className="shrink-0">
          <Logo tam="1.6rem" />
        </Link>
        <nav
          aria-label="Navegación principal"
          className="hidden lg:flex items-center h-full gap-6 text-sm font-bold"
        >
          {LINKS.map((p) => (
            <Link
              key={p.href}
              href={p.href}
              aria-current={activo(p.href, path) ? "page" : undefined}
              className={`flex items-center h-full border-b-2 ${activo(p.href, path) ? "border-acc text-txt" : "border-transparent text-mut hover:text-txt"}`}
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
      </div>
      {["/", "/cara", "/tabla", "/liga"].includes(path) && (
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
                className={`flex items-center gap-2 shrink-0 min-h-11 text-xs font-bold border-b-2 ${liga === k ? "border-acc text-txt" : "border-transparent text-mut"}`}
              >
                <LigaLogo liga={k} size={22} />
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
  return (
    <nav
      aria-label="Navegación móvil"
      className="lg:hidden fixed bottom-0 inset-x-0 z-40 bg-card border-t border-line2 safe-b"
    >
      <div className="grid grid-cols-3 max-w-xl mx-auto">
        {LINKS.map((p) => (
          <Link
            key={p.href}
            href={p.href}
            aria-current={activo(p.href, path) ? "page" : undefined}
            className={`relative flex flex-col items-center gap-1 py-2.5 min-h-[60px] text-[.7rem] font-bold ${activo(p.href, path) ? "text-acc" : "text-mut"}`}
          >
            <Icono d={p.icono} />
            {p.nombre}
            {p.href === "/boleto" && boleto.length > 0 && (
              <span className="absolute top-1 right-[30%] primary text-[10px] px-1.5 rounded-full">
                {boleto.length}
              </span>
            )}
          </Link>
        ))}
      </div>
    </nav>
  );
}

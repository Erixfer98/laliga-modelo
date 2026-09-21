"use client";
// Navegación tipo app: arriba la marca y las ligas (con logo); abajo, en celular, una barra de pestañas con iconos.
// En pantallas grandes las pestañas suben junto a la marca.
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LIGAS } from "@/lib/api";
import { useStore } from "@/lib/store";
import { LigaLogo } from "./Crest";
import { Logo } from "./Logo";

const P = { home: "M3 11 12 3l9 8v10h-6v-6H9v6H3z", ball: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 4 3.5 2.6-1.3 4.2H9.8L8.5 9.6Zm-7 4.5 2.5-1.2M19 11.5l-2.5-1.2M8.4 18.6l1.6-2.4M15.6 18.6 14 16.2",
  ticket: "M3 8a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4Zm7-2v12",
  h2h: "M4 8h13l-3-3M20 16H7l3 3", table: "M4 6h16M4 12h16M4 18h16", book: "M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2Zm0 0v16" };

export function Icono({ d, size = 22 }: { d: string; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>;
}

const PAGINAS = [
  { href: "/", nombre: "Inicio", icono: P.home },
  { href: "/partido", nombre: "Partido", icono: P.ball },
  { href: "/boleto", nombre: "Boleto", icono: P.ticket },
  { href: "/cara", nombre: "Cara a cara", icono: P.h2h },
  { href: "/tabla", nombre: "Tabla", icono: P.table },
  { href: "/diccionario", nombre: "Glosario", icono: P.book },
];
const CON_LIGA = ["/", "/partido", "/cara", "/tabla"];

export function Header() {
  const path = usePathname();
  const { liga, setLiga, boleto } = useStore();
  const activa = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));
  return (
    <header className="sticky top-0 z-40 bg-bg/90 backdrop-blur-md">
      <div className="max-w-[640px] mx-auto px-4 pt-3 pb-1">
        <div className="flex items-center gap-3">
          <Link href="/"><Logo tam="1.5rem" animado /></Link>
          <nav className="hidden sm:flex gap-1 ml-2">
            {PAGINAS.map((p) => (
              <Link key={p.href} href={p.href} className={`rounded-full px-2.5 py-1.5 text-[0.8rem] font-bold whitespace-nowrap ${activa(p.href) ? "bg-card2 text-txt" : "text-mut hover:text-txt"}`}>
                {p.nombre}{p.href === "/boleto" && boleto.length > 0 && <span className="ml-1.5 inline-flex items-center justify-center min-w-[18px] h-[18px] rounded-full bg-acc text-white text-[0.66rem] px-1">{boleto.length}</span>}
              </Link>
            ))}
          </nav>
          <span className="ml-auto sm:hidden text-[0.66rem] font-bold text-mut2 uppercase tracking-[0.1em] opacity-70">Parlays con datos</span>
        </div>
        {CON_LIGA.includes(path) && (
          <div className="scrollx flex gap-2 mt-2.5 -mx-1 px-1 pb-1.5">
            {Object.keys(LIGAS).map((k) => (
              <button key={k} type="button" onClick={() => setLiga(k)}
                className={`shrink-0 flex items-center gap-2 rounded-full pl-1 pr-3 py-1 text-[0.8rem] font-bold transition-colors ${k === liga ? "bg-txt text-bg" : "bg-card2 text-mut hover:text-txt"}`}>
                <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full ${k === liga ? "bg-white" : "bg-card"}`}><LigaLogo liga={k} size={20} /></span>
                {LIGAS[k]}
              </button>
            ))}
          </div>
        )}
      </div>
    </header>
  );
}

export function BarraInferior() {
  const path = usePathname();
  const { boleto } = useStore();
  const activa = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));
  return (
    <nav className="sm:hidden fixed bottom-0 inset-x-0 z-40 bg-card/95 backdrop-blur-md border-t border-line2 safe-b">
      <div className="max-w-[640px] mx-auto grid grid-cols-6">
        {PAGINAS.map((p) => (
          <Link key={p.href} href={p.href} className={`relative flex flex-col items-center gap-0.5 pt-2 pb-1.5 text-[0.62rem] font-bold ${activa(p.href) ? "text-txt" : "text-mut2"}`}>
            <span className={`rounded-full px-3 py-0.5 ${activa(p.href) ? "bg-acc/20 text-acc" : ""}`}><Icono d={p.icono} /></span>
            {p.nombre}
            {p.href === "/boleto" && boleto.length > 0 && <span className="absolute top-1 right-[18%] min-w-[16px] h-4 rounded-full bg-acc text-white text-[0.6rem] leading-4 text-center px-1">{boleto.length}</span>}
          </Link>
        ))}
      </div>
    </nav>
  );
}

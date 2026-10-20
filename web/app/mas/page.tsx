// Más: lo secundario de Kuota, fuera de la pantalla de partido.
import Link from "next/link";
import { Apariencia } from "@/components/Nav";

const LINKS = [
  { href: "/liga", nombre: "Resumen de la liga", desc: "Medias por mercado y pulso de los equipos" },
  { href: "/tabla", nombre: "Tabla de posiciones", desc: "Temporada actual y anteriores" },
  { href: "/cara", nombre: "Cara a cara completo", desc: "Todas las métricas de cada enfrentamiento" },
  { href: "/diccionario", nombre: "Glosario", desc: "Qué significa cada término" },
];

export default function Mas() {
  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="page-title mb-4">Más</h1>
      <nav aria-label="Más secciones" className="rounded-card bg-card border border-line2 px-4">
        {LINKS.map((l) => (
          <Link key={l.href} href={l.href} className="flex items-center justify-between gap-3 min-h-16 border-b border-line2 last:border-0">
            <span>
              <span className="block font-bold">{l.nombre}</span>
              <span className="block text-xs text-mut">{l.desc}</span>
            </span>
            <span aria-hidden="true" className="text-mut">→</span>
          </Link>
        ))}
      </nav>
      <div className="rounded-card bg-card border border-line2 p-4 mt-4">
        <Apariencia />
        {process.env.KUOTA_CLAVE && (
          <form method="POST" action="/api/salir" className="mt-3 border-t border-line2 pt-2">
            <button className="min-h-11 text-sm text-mut font-semibold w-full text-left">Cerrar sesión</button>
          </form>
        )}
      </div>
    </div>
  );
}

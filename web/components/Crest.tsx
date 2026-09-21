"use client";
// Escudo de un equipo (o sus iniciales si no hay escudo) y logo de liga.
import { useState } from "react";
import { LIGAS } from "@/lib/api";
import { useLogos } from "@/lib/logos";

/** Iniciales de un equipo: "Real Madrid" -> "RM", "Barcelona" -> "BA", "St. Pauli" -> "SP". */
export function iniciales(nombre: string) {
  const p = nombre.replace(/[^\p{L}\p{N} ]/gu, " ").split(/\s+/).filter(Boolean);
  return (p.length >= 2 ? p[0][0] + p[1][0] : (p[0] ?? "?").slice(0, 2)).toUpperCase();
}

export function Crest({ liga, equipo, size = 36, lado, className = "" }: { liga: string; equipo: string; size?: number; lado?: "l" | "v"; className?: string }) {
  const logos = useLogos();
  const [roto, setRoto] = useState(false);
  const url = logos.equipos[liga]?.[equipo];
  const fondo = lado === "v" ? "var(--vis)" : "var(--acc)";
  if (url && !roto) {
    return (
      <span className={`inline-flex items-center justify-center shrink-0 rounded-full bg-white/90 ${className}`} style={{ width: size, height: size }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={url} alt={equipo} width={size - 8} height={size - 8} style={{ width: size - 8, height: size - 8, objectFit: "contain" }} onError={() => setRoto(true)} />
      </span>
    );
  }
  return (
    <span className={`inline-flex items-center justify-center shrink-0 rounded-full font-extrabold text-white ${className}`}
      style={{ width: size, height: size, background: fondo, fontSize: size * 0.34, letterSpacing: "-0.02em" }} title={equipo}>
      {iniciales(equipo)}
    </span>
  );
}

export function LigaLogo({ liga, size = 28, className = "" }: { liga: string; size?: number; className?: string }) {
  const logos = useLogos();
  const [roto, setRoto] = useState(false);
  const url = logos.ligas[liga]?.logo;
  if (url && !roto) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={url} alt={LIGAS[liga] ?? liga} width={size} height={size} className={`shrink-0 object-contain ${className}`} style={{ width: size, height: size }} onError={() => setRoto(true)} />;
  }
  const abrev: Record<string, string> = { laliga: "ES", premier: "EN", seriea: "IT", bundesliga: "DE", ligue1: "FR", ligamx: "MX" };
  return (
    <span className={`inline-flex items-center justify-center shrink-0 rounded-full bg-card2 text-mut font-extrabold ${className}`} style={{ width: size, height: size, fontSize: size * 0.36 }}>
      {abrev[liga] ?? "?"}
    </span>
  );
}

"use client";
// Logo de Kuota: la "o" es una pelota. Con `animado`, la pelota entra dando botes cada vez más cortos y se aplasta al caer
// en su lugar (el resto del logo tiembla al recibirla). Se usa en la pantalla de contraseña y en la barra superior.

function Pelota({ className = "" }: { className?: string }) {
  // pelota clásica simplificada: círculo claro, pentágono central y cinco parches hacia el borde (dibujo propio, sin marcas)
  const c = 50, r = 46;
  const pent = (cx: number, cy: number, rad: number, giro: number) =>
    Array.from({ length: 5 }, (_, i) => { const a = ((giro + i * 72) * Math.PI) / 180; return `${(cx + rad * Math.cos(a)).toFixed(1)},${(cy + rad * Math.sin(a)).toFixed(1)}`; }).join(" ");
  return (
    <svg viewBox="0 0 100 100" className={className} aria-hidden="true">
      <defs><clipPath id="pelota-clip"><circle cx={c} cy={c} r={r - 1} /></clipPath></defs>
      <circle cx={c} cy={c} r={r} fill="#f4f4f6" />
      <g clipPath="url(#pelota-clip)" fill="#0a0d14">
        <polygon points={pent(c, c, 17, -90)} />
        {Array.from({ length: 5 }, (_, i) => { const a = ((-90 + 36 + i * 72) * Math.PI) / 180;
          return <polygon key={i} points={pent(c + 43 * Math.cos(a), c + 43 * Math.sin(a), 15, -90 + 36 + i * 72 + 36)} />; })}
      </g>
      <circle cx={c} cy={c} r={r} fill="none" stroke="#0a0d14" strokeWidth="4" />
    </svg>
  );
}

export function Logo({ tam = "1.5rem", animado = false, className = "" }: { tam?: string; animado?: boolean; className?: string }) {
  return (
    <span className={`num inline-flex items-baseline tracking-[-0.04em] leading-none select-none ${animado ? "logo-anim" : ""} ${className}`} style={{ fontSize: tam }}>
      <span className="logo-ku">Ku</span>
      <span className="logo-pelota inline-block align-baseline" style={{ width: "0.84em", height: "0.84em", margin: "0 0.07em 0 0.05em", transform: "translateY(0.1em)", willChange: "transform" }}>
        <Pelota className="w-full h-full block logo-bola" />
      </span>
      <span className="logo-ta">ta<span className="text-acc">.</span></span>
    </span>
  );
}

"use client";
// Pantalla de contraseña (se muestra cuando KUOTA_CLAVE está definida y el navegador no tiene la cookie).
import { useEffect, useState } from "react";

export function Puerta() {
  const [error, setError] = useState(false);
  useEffect(() => { setError(new URLSearchParams(window.location.search).has("error")); }, []);
  return (
    <main className="min-h-dvh flex items-center justify-center px-6">
      <form method="POST" action="/api/entrar" className="hero rounded-card w-full max-w-[360px] px-6 py-8 text-center">
        <div className="num text-[2rem]">Kuota<span className="text-acc">.</span></div>
        <div className="text-[0.82rem] text-mut mt-1 mb-6">Parlays con datos · acceso privado</div>
        <input className="ctl text-center text-[1.05rem] font-bold" type="password" name="clave" placeholder="Contraseña" autoFocus autoComplete="current-password" />
        {error && <div className="text-bad text-[0.82rem] font-bold mt-2">Contraseña incorrecta</div>}
        <button type="submit" className="mt-3 w-full rounded-2xl bg-acc text-white font-bold min-h-[46px]">Entrar</button>
      </form>
    </main>
  );
}

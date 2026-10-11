"use client";
// Pantalla de contraseña (se muestra cuando KUOTA_CLAVE está definida y el navegador no tiene la cookie).
import { useEffect, useState } from "react";
import { Logo } from "./Logo";

export function Puerta() {
  const [error, setError] = useState(false);
  useEffect(() => {
    setError(new URLSearchParams(window.location.search).has("error"));
  }, []);
  return (
    <main className="min-h-dvh flex items-center justify-center px-6">
      <form
        method="POST"
        action="/api/entrar"
        className="hero rounded-card w-full max-w-[360px] px-6 py-8 text-center"
      >
        <h1 className="py-2" aria-label="Kuota">
          <Logo tam="3rem" />
        </h1>
        <div className="text-[0.82rem] text-mut mt-1 mb-6">
          El fútbol, con perspectiva · acceso privado
        </div>
        <label className="block text-sm text-mut mb-2" htmlFor="clave">
          Contraseña de acceso
        </label>
        <input
          id="clave"
          required
          className="ctl text-center text-[1.05rem] font-bold"
          type="password"
          name="clave"
          placeholder="Contraseña"
          autoFocus
          autoComplete="current-password"
        />
        {error && (
          <div role="alert" className="text-bad text-[0.82rem] font-bold mt-2">
            Contraseña incorrecta
          </div>
        )}
        <button
          type="submit"
          className="mt-3 w-full rounded-2xl primary font-bold min-h-[46px]"
        >
          Entrar
        </button>
      </form>
    </main>
  );
}

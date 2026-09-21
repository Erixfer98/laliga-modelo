"use client";
// Hook para pedir una vista a la API: devuelve datos, error y si está cargando. Mantiene los datos anteriores mientras llega la nueva respuesta.
import { useEffect, useState } from "react";
import { api } from "./api";

type Params = Record<string, string | number | boolean | null | undefined>;

export function useApi<T>(path: string | null, params: Params = {}) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!!path);
  const clave = JSON.stringify([path, params]);

  useEffect(() => {
    if (!path) return;
    let vivo = true;
    setLoading(true); setError(null);
    api<T>(path, params)
      .then((d) => { if (vivo) { setData(d); setLoading(false); } })
      .catch((e: Error) => { if (vivo) { setError(e.message); setLoading(false); } });
    return () => { vivo = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clave]);

  return { data, error, loading };
}

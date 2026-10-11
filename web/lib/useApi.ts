"use client";
import { useEffect, useState } from "react";
import { api } from "./api";
type Params = Record<string, string | number | boolean | null | undefined>;
/** Une la respuesta a su contexto; nunca muestra datos de otra liga o filtro. */
export function useApi<T>(path: string | null, params: Params = {}) {
  const [revision, setRevision] = useState(0);
  const key = JSON.stringify([
    path,
    Object.entries(params).sort(([a], [b]) => a.localeCompare(b)),
    revision,
  ]);
  const [result, setResult] = useState<{
    key: string;
    data: T | null;
    error: string | null;
    pending: boolean;
  }>({ key: "", data: null, error: null, pending: false });
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    setResult({ key, data: null, error: null, pending: true });
    api<T>(path, params, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted)
          setResult({ key, data, error: null, pending: false });
      })
      .catch((e: Error) => {
        if (!controller.signal.aborted)
          setResult({ key, data: null, error: e.message, pending: false });
      });
    return () => controller.abort();
    // La clave incluye todos los parámetros y la revisión del reintento.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  const active = path && result.key === key;
  return {
    data: active ? result.data : null,
    error: active ? result.error : null,
    loading: !!path && (!active || result.pending),
    reintentar: () => setRevision((v) => v + 1),
  };
}

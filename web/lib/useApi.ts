"use client";
import { useEffect, useState } from "react";
import { api } from "./api";
const cache = new Map<string, { data: unknown; at: number; bytes: number }>();
let bytesCache = 0;
function guardar(key: string, data: unknown) {
  const bytes = JSON.stringify(data).length * 2;
  const old = cache.get(key);
  if (old) {
    bytesCache -= old.bytes;
    cache.delete(key);
  }
  if (bytes > 2 * 1024 * 1024) return;
  while (
    cache.size &&
    (cache.size >= 8 || bytesCache + bytes > 2 * 1024 * 1024)
  ) {
    const first = cache.keys().next().value!;
    bytesCache -= cache.get(first)!.bytes;
    cache.delete(first);
  }
  cache.set(key, { data, at: Date.now(), bytes });
  bytesCache += bytes;
}
type Params = Record<string, string | number | boolean | null | undefined>;
/** Cancela respuestas obsoletas. scope permite conservar controles del mismo partido
 * durante una actualización; el consumidor debe marcar pendientes y bloquear acciones.
 * Una respuesta en caché siempre se revalida antes de autorizar el boleto. */
export function useApi<T>(
  path: string | null,
  params: Params = {},
  options: { cache?: boolean; scope?: string } = {},
) {
  const [revision, setRevision] = useState(0);
  const cacheKey = JSON.stringify([
    path,
    Object.entries(params).sort(([a], [b]) => a.localeCompare(b)),
  ]);
  const saved = options.cache ? cache.get(cacheKey) : undefined;
  const cached =
    saved && Date.now() - saved.at < 30000 ? (saved.data as T) : null;
  const key = JSON.stringify([
    path,
    Object.entries(params).sort(([a], [b]) => a.localeCompare(b)),
    revision,
  ]);
  const [result, setResult] = useState<{
    key: string;
    scope?: string;
    data: T | null;
    error: string | null;
    pending: boolean;
  }>({ key: "", data: null, error: null, pending: false });
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    setResult((previous) => ({
      key,
      scope: options.scope,
      data:
        cached ??
        (options.scope && previous.scope === options.scope
          ? previous.data
          : null),
      error: null,
      pending: true,
    }));
    api<T>(path, params, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          if (options.cache) guardar(cacheKey, data);
          setResult({
            key,
            scope: options.scope,
            data,
            error: null,
            pending: false,
          });
        }
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
    data: active
      ? result.data
      : (cached ??
        (options.scope && result.scope === options.scope ? result.data : null)),
    error: active ? result.error : null,
    loading: !!path && (!active || result.pending),
    reintentar: () => setRevision((v) => v + 1),
  };
}

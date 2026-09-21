// Cliente de la API de Kuota (api.py). Todo lo que calcula vive en Python; aquí solo se pide y se tipa.
// La URL de la API se configura con NEXT_PUBLIC_API_URL (por defecto, la API local).

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const LIGAS: Record<string, string> = {
  laliga: "La Liga", premier: "Premier League", seriea: "Serie A", bundesliga: "Bundesliga", ligue1: "Ligue 1", ligamx: "Liga MX",
};
export const METRICAS: Record<string, string> = {
  goles: "Goles", goles_1t: "Goles 1er tiempo", goles_2t: "Goles 2do tiempo", tiros: "Tiros", tiros_a_puerta: "Tiros a puerta",
  corners: "Corners", faltas: "Faltas", amarillas: "Tarjetas amarillas", rojas: "Tarjetas rojas",
};
export const METRICA_CORTA: Record<string, string> = {
  goles: "Goles", goles_1t: "Goles 1T", goles_2t: "Goles 2T", tiros: "Tiros", tiros_a_puerta: "Tiros a puerta",
  corners: "Corners", faltas: "Faltas", amarillas: "Amarillas", rojas: "Rojas",
};

// ---------------------------------------------------------------- tipos (espejo de kuota.vista_*)
export type Media = { metrica: string; nombre: string; local: number; visitante: number; total: number; linea: number; pct_over: number; decimales: number };
export type FilaTabla = { equipo: string; J: number; G: number; E: number; P: number; GF: number; GC: number; PTS: number; DG: number; forma: string[] };
export type Tendencia = { equipo: string; prom: number; favor: number; contra: number };
export type Validacion = { partidos: number; ultimo: string; equipos: number; vacias: number; duplicados: number; errores: string[]; avisos: string[]; ok: boolean } | null;

export type VistaInicio = {
  liga: string; nombre: string; temporada: string; ultimo: string; partidos_temporada: number; partidos_total: number;
  equipos: string[]; torneos_recientes: string[]; validacion: Validacion; medias: Media[]; tabla: FilaTabla[];
  tendencias: { metrica: string; n: number; media_liga: number; filas: Tendencia[] };
};
export type VistaTabla = { liga: string; nombre: string; temporada: string; temporadas: string[]; tabla: FilaTabla[] };

export type PartidoCara = {
  fecha: string; temporada: string; local: string; visitante: string; goles_local: number | null; goles_visitante: number | null;
  resultado: "g" | "e" | "p" | null; metricas: Record<string, { local: number | null; visitante: number | null }>;
};
export type VistaCara = { liga: string; nombre: string; local: string; visitante: string; torneos: string[]; solo_casa: boolean; n: number; G: number; E: number; P: number; partidos: PartidoCara[] };

export type Var = { equipo: string; condicion: string; estado: string; ratio: number; n_ef: number };
export type Mercado = {
  mercado: string; grupo: string; prob: number; lo: number; hi: number; col_l: string; col_v: string; linea: number; over: boolean;
  hl: number; nl: number; hv: number; nv: number; tasa: number; cal: string; cls: string; serie_l: boolean[]; serie_v: boolean[]; volatil: boolean; tag: string;
};
export type Hist = { fecha: string; condicion: string; rival: string; marcador: string; a_favor: number; en_contra: number; total: number };
export type StatCol = { media: number; mediana: number; desv: number; min: number; max: number; pct: number };
export type Stats = { a_favor: StatCol; en_contra: StatCol; total: StatCol } | null;
export type Grafico =
  | { tipo: "matriz"; k: number; max: number; celdas: { p: number; gana: boolean }[][] }
  | { tipo: "distribucion" | "diferencia"; valores: { x: number; p: number; gana: boolean }[] };
export type Pata = Mercado & { grafico: Grafico; historial_local: Hist[]; historial_visitante: Hist[]; stats_local: Stats; stats_visitante: Stats };
export type Cfg = Record<string, [number, number]>;

export type VistaPartido = {
  liga: string; nombre_liga: string; partido: string; metrica: string; nombre: string; local: string; visitante: string;
  lambda_local: number; lambda_visitante: number; rango: { local: [number, number]; visitante: [number, number]; total: [number, number] };
  var: { local: Var; visitante: Var }; vol: Record<string, boolean>; medias_liga: { local: number; visitante: number; total: number };
  cfg: Cfg; grupos: string[]; n: number; filtro: string; mercados: Mercado[]; pata: Pata; contexto_armar: string; contexto_analizar: string;
};

export type Leg = { partido: string; metrica: string; mercado: string; prob: number; cuota: number; cal: string; cls: string; lo: number; hi: number };
export type ResumenBoleto = { n: number; prob: number; cuota: number; ev: number; lo: number; hi: number; ev_lo: number; ev_hi: number; justa: number; mismo_partido: boolean } | null;
export type Stake = { kelly: number; sin_valor: boolean; banca: number; opciones: { nombre: string; fraccion: number; monto: number }[] } | null;
export type Diccionario = { grupo: string; descripcion: string; items: { termino: string; definicion: string }[] }[];

// ---------------------------------------------------------------- llamadas
export async function api<T>(path: string, params: Record<string, string | number | boolean | null | undefined> = {}): Promise<T> {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined && v !== "") q.set(k, String(v));
  const url = `${API_URL}${path}${q.toString() ? `?${q}` : ""}`;
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(`API ${r.status} en ${path}: ${(await r.text()).slice(0, 200)}`);
  return r.json();
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API_URL}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`API ${r.status} en ${path}`);
  return r.json();
}

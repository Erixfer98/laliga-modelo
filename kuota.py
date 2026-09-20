"""
kuota.py — Motor de Kuota: todo lo que calcula la app, sin nada de pantalla.

Cada funcion recibe los datos (df de modelo.cargar) y parametros, y devuelve numeros, dicts y listas.
Ni Streamlit ni HTML: lo mismo lo usa app.py (pantalla actual), la API (pantalla nueva) y cualquier script.
a_json(x) convierte cualquier resultado a tipos puros de Python (listo para JSON).

Bloques:  datos · resumen de liga · tabla y tendencias · historial y calificacion · mercados · analisis de un partido ·
          graficos del modelo · cara a cara · boleto y stake · vistas (paquetes completos) · contexto IA · diccionario

Prueba rapida:  python kuota.py laliga "Real Madrid" "Barcelona" corners   -> imprime la vista de partido en JSON
"""

import json
import math
import os
import sys
from datetime import date, datetime

import numpy as np
import pandas as pd

import modelo as mo

LIGAS = {"laliga": "La Liga", "premier": "Premier League", "seriea": "Serie A", "bundesliga": "Bundesliga", "ligue1": "Ligue 1", "ligamx": "Liga MX"}
GOL = ("goles", "goles_1t", "goles_2t")
MAYOR_NUMERO = ("tiros", "tiros_a_puerta", "corners", "faltas", "amarillas")   # metricas con mercado "quien hace mas"
NOM = mo.NOMBRES
NOM_CORTO = {"goles": "Goles", "goles_1t": "Goles 1T", "goles_2t": "Goles 2T", "tiros": "Tiros", "tiros_a_puerta": "Tiros a puerta",
             "corners": "Corners", "faltas": "Faltas", "amarillas": "Amarillas", "rojas": "Rojas"}
NIVELES = [("Excelente", "exc"), ("Buena", "bue"), ("Regular", "reg"), ("Mala", "mal"), ("Pésima", "pes")]
CARPETA_DATOS = "datos"


# ================================================================== datos
def ligas_disponibles(carpeta: str = CARPETA_DATOS) -> dict:
    return {k: v for k, v in LIGAS.items() if os.path.exists(f"{carpeta}/bbdd_{k}.csv")} or {"laliga": "La Liga"}


def cargar(liga: str, carpeta: str = CARPETA_DATOS) -> pd.DataFrame:
    return mo.cargar(f"{carpeta}/bbdd_{liga}.csv")


def incertidumbre(df: pd.DataFrame, met: str) -> pd.DataFrame:
    """Incertidumbre de la lambda por equipo y condicion + variabilidad vs liga (ver modelo.incertidumbre)."""
    return mo.incertidumbre(df, met)


def equipos(df: pd.DataFrame) -> list:
    return mo.equipos(df)


def validacion(carpeta: str = CARPETA_DATOS) -> dict:
    """Reporte de calidad de datos que deja validar_bbdd.py (o None si todavia no existe)."""
    ruta = f"{carpeta}/validacion.json"
    return json.load(open(ruta)) if os.path.exists(ruta) else None


# ================================================================== resumen de liga
def temporada_actual(df: pd.DataFrame) -> str:
    return df.sort_values("fecha")["temporada_txt"].iloc[-1]


def temporadas(df: pd.DataFrame) -> list:
    return sorted(df.temporada_txt.unique(), reverse=True)


def torneos_recientes(df: pd.DataFrame) -> list:
    """Torneo vigente y el anterior (los dos ultimos por fecha), en orden cronologico."""
    return df.groupby("temporada_txt")["fecha"].max().sort_values().index.tolist()[-2:]


def resumen_liga(df: pd.DataFrame) -> dict:
    temp = temporada_actual(df)
    return {"temporada": temp, "ultimo": df["fecha"].max(), "partidos_temporada": int((df.temporada_txt == temp).sum()),
            "partidos_total": len(df), "equipos": equipos(df), "torneos_recientes": torneos_recientes(df)}


def medias_por_metrica(df: pd.DataFrame) -> list:
    """Medias de la liga por metrica (todas las temporadas cargadas), la linea .5 mas cercana a la media del total
    y el % de partidos por encima de esa linea."""
    filas = []
    for met, (col_l, col_v, _) in mo.METRICAS.items():
        d = df.dropna(subset=[col_l, col_v]); tot = d[col_l] + d[col_v]
        ln = float(np.floor(tot.mean()) + 0.5)
        filas.append({"metrica": met, "nombre": NOM_CORTO[met], "local": float(d[col_l].mean()), "visitante": float(d[col_v].mean()),
                      "total": float(tot.mean()), "linea": ln, "pct_over": float((tot > ln).mean()),
                      "decimales": 2 if met in GOL or met == "rojas" else 1})
    return filas


# ================================================================== tabla de posiciones y tendencias
def tabla_posiciones(df: pd.DataFrame, temp: str) -> list:
    """Una fila por equipo: J G E P GF GC DG PTS y forma (lista g/e/p, antiguo -> reciente). Ordenada por PTS, DG, GF."""
    d = df[df.temporada_txt == temp]
    filas = {}
    for _, g in d.sort_values("fecha").iterrows():
        gl, gv = int(g.goles_local_val), int(g.goles_visitante_val)
        for eq, gf, gc in ((g.equipo_local_txt, gl, gv), (g.equipo_visitante_txt, gv, gl)):
            f = filas.setdefault(eq, {"equipo": eq, "J": 0, "G": 0, "E": 0, "P": 0, "GF": 0, "GC": 0, "PTS": 0, "forma": []})
            f["J"] += 1; f["GF"] += gf; f["GC"] += gc
            res = "g" if gf > gc else ("p" if gf < gc else "e")
            f["G" if res == "g" else ("P" if res == "p" else "E")] += 1
            f["PTS"] += 3 if res == "g" else (1 if res == "e" else 0)
            f["forma"].append(res)
    t = pd.DataFrame(filas.values())
    if t.empty:
        return []
    t["DG"] = t.GF - t.GC
    return t.sort_values(["PTS", "DG", "GF"], ascending=False).reset_index(drop=True).to_dict("records")


def tendencias(df: pd.DataFrame, met: str, n: int = 5) -> dict:
    """Equipos con mayor y menor promedio total de la metrica en sus ultimos n partidos, vs media liga."""
    ml = mo.medias_liga(df, met)
    filas = []
    for eq in equipos(df):
        h = mo.ultimos_n(df, eq, met, n)
        if len(h) >= 3:
            filas.append({"equipo": eq, "prom": h.total.mean(), "favor": h.a_favor.mean(), "contra": h.en_contra.mean()})
    t = pd.DataFrame(filas).sort_values("prom", ascending=False)
    return {"metrica": met, "n": n, "media_liga": float(ml["total"]), "filas": t.to_dict("records")}


# ================================================================== historial y calificacion
def historial(df: pd.DataFrame, equipo: str, met: str, n: int, condicion: str = None) -> pd.DataFrame:
    """Ultimos n partidos del equipo (opcional: solo "Casa" o "Fuera") con la metrica a favor / en contra / total
    y las banderas gano, empato, perdio, no_perdio, no_gano, btts."""
    h = mo.ultimos_n(df, equipo, met, 80)
    if condicion:
        h = h[h.condicion == condicion]
    h = h.head(n).copy()
    h["gano"] = (h.a_favor > h.en_contra).astype(int)
    h["empato"] = (h.a_favor == h.en_contra).astype(int)
    h["perdio"] = (h.a_favor < h.en_contra).astype(int)
    h["no_perdio"] = 1 - h.perdio
    h["no_gano"] = 1 - h.gano
    h["btts"] = ((h.a_favor > 0) & (h.en_contra > 0)).astype(int)
    return h


def historial_json(h: pd.DataFrame) -> list:
    return h.to_dict("records")


def cumple(h: pd.DataFrame, mk: dict, lado: str) -> pd.Series:
    """Serie True/False: en que partidos del historial se habria cumplido la pata (lado "l" = local, "v" = visitante)."""
    col = mk["col_l"] if lado == "l" else mk["col_v"]
    return (h[col] > mk["linea"]) if mk["over"] else (h[col] < mk["linea"])


def calificar(p: float, tasa: float) -> tuple:
    """60% probabilidad Poisson + 40% cumplimiento historico -> (texto, clase)."""
    s = 0.6 * p + 0.4 * tasa
    for lim, txt, cls in ((0.78, "Excelente", "exc"), (0.68, "Buena", "bue"), (0.56, "Regular", "reg"), (0.45, "Mala", "mal")):
        if s >= lim:
            return txt, cls
    return "Pésima", "pes"


def bajar_nivel(cls: str) -> tuple:
    return NIVELES[min([c for _, c in NIVELES].index(cls) + 1, len(NIVELES) - 1)]


def kelly(p: float, cuota: float) -> float:
    """Fraccion de banca segun Kelly: (b*p - q) / b, con b = cuota - 1. Negativa = sin valor."""
    b = cuota - 1
    return (b * p - (1 - p)) / b if b > 0 else 0.0


def evaluar(mk: dict, hl: pd.DataFrame, hv: pd.DataFrame, vol: dict = None) -> dict:
    """Cumplimiento historico de la pata en los dos historiales + calificacion.
    vol = {equipo: True si es volátil en su condicion}. La pata baja un nivel si algún equipo que participa en la pata
    es volátil (Total/Resultado/Mayor número = los dos; grupo de un equipo = ese)."""
    cl, cv = cumple(hl, mk, "l"), cumple(hv, mk, "v")
    n = len(hl) + len(hv)
    tasa = (cl.sum() + cv.sum()) / n if n else 0
    txt, cls = calificar(mk["prob"], tasa)
    equipos_pata = list(vol) if (vol and mk["grupo"] in ("Resultado", "Total", "Mayor número")) else [mk["grupo"]]
    volatil = bool(vol) and any(vol.get(t, False) for t in equipos_pata)
    if volatil:
        txt, cls = bajar_nivel(cls)
    return {"hl": int(cl.sum()), "nl": len(hl), "hv": int(cv.sum()), "nv": len(hv), "tasa": float(tasa), "cal": txt, "cls": cls,
            "serie_l": [bool(x) for x in cl], "serie_v": [bool(x) for x in cv], "volatil": volatil, "tag": ("↕ " if volatil else "") + txt}


def stats_historial(h: pd.DataFrame, linea: float, over: bool) -> dict:
    """Media, mediana, desviacion, min, max y % cumple para a favor / en contra / total (None si no hay partidos)."""
    if h.empty:
        return None

    def col(c):
        s = h[c]; pct = ((s > linea) if over else (s < linea)).mean()
        return {"media": float(s.mean()), "mediana": float(s.median()), "desv": float(s.std(ddof=0)),
                "min": float(s.min()), "max": float(s.max()), "pct": float(pct)}
    return {"a_favor": col("a_favor"), "en_contra": col("en_contra"), "total": col("total")}


# ================================================================== mercados (linea configurable)
def lineas(centro: float, rango: int) -> list:
    return [x for x in np.arange(centro - rango, centro + rango + 0.01, 1.0) if x > 0]


def centro_defecto(lam: float, met: str) -> float:
    if met == "goles": return 2.5
    if met in GOL: return 1.5
    if met == "rojas": return 0.5
    return max(round(lam) - 0.5, 0.5)


def cfg_defecto(lam_l: float, lam_v: float, met: str, local: str, visitante: str) -> dict:
    """Lineas iniciales por grupo: {grupo: [centro, ± lineas]}."""
    return {"Total": [centro_defecto(lam_l + lam_v, met), 2 if met == "goles" else 1],
            local: [centro_defecto(lam_l, met), 1], visitante: [centro_defecto(lam_v, met), 1]}


def mercados(r: dict, met: str, local: str, visitante: str, cfg: dict) -> list:
    """cfg = {grupo: (centro, rango)}. Devuelve lista de mercados con su regla de evaluacion historica. Cada mercado
    trae prob (lambda central) y lo / hi = pesimista / optimista: la misma probabilidad calculada en las esquinas
    bajo/alto de las lambdas (minimo y maximo de las 4 esquinas; en mercados de un solo equipo, de sus 2 extremos).
    Todo sale de las mismas lambdas bajo-alto que se muestran arriba. "region" (funcion) marca en la matriz los
    marcadores con los que gana la pata; a_json la quita."""
    m, lam_l, lam_v = r["matriz"], r["lambda_local"], r["lambda_visitante"]
    esq, (ll, lh), (vl, vh) = r["rango"]["esquinas"], r["rango"]["lam_l"], r["rango"]["lam_v"]
    k = m.shape[0]; tot = np.add.outer(np.arange(k), np.arange(k))
    out = []

    def add(nombre, grupo, f, col_l, col_v, linea, over, region):
        """f(matriz) -> probabilidad; se evalua en la matriz central y en las 4 esquinas."""
        p, ps = f(m), [f(e) for e in esq.values()]
        out.append({"mercado": nombre, "grupo": grupo, "prob": float(min(max(p, 0), 1)),
                    "lo": float(min(max(min(ps), 0), 1)), "hi": float(min(max(max(ps), 0), 1)),
                    "col_l": col_l, "col_v": col_v, "linea": linea, "over": over, "region": region})

    def add1(nombre, grupo, lam, lam_lo, lam_hi, ln, over, col_l, col_v, region):
        """mercado de un solo equipo: Poisson con su lambda central, baja y alta."""
        ps = [mo.prob_over(x, ln) for x in (lam, lam_lo, lam_hi)]
        if not over: ps = [1 - x for x in ps]
        out.append({"mercado": nombre, "grupo": grupo, "prob": float(ps[0]), "lo": float(min(ps[1:])), "hi": float(max(ps[1:])),
                    "col_l": col_l, "col_v": col_v, "linea": ln, "over": over, "region": region})

    p1 = lambda x: np.tril(x, -1).sum(); px = lambda x: np.trace(x); p2 = lambda x: np.triu(x, 1).sum(); bt = lambda x: x[1:, 1:].sum()
    # quien gana / quien hace mas: sale de la matriz
    if met in GOL:
        add(f"Gana {local}", "Resultado", p1, "gano", "perdio", 0.5, True, lambda x, y: x > y)
        add("Empate", "Resultado", px, "empato", "empato", 0.5, True, lambda x, y: x == y)
        add(f"Gana {visitante}", "Resultado", p2, "perdio", "gano", 0.5, True, lambda x, y: x < y)
        add(f"{local} o empate", "Resultado", lambda x: p1(x) + px(x), "no_perdio", "no_gano", 0.5, True, lambda x, y: x >= y)
        add(f"{visitante} o empate", "Resultado", lambda x: p2(x) + px(x), "no_gano", "no_perdio", 0.5, True, lambda x, y: x <= y)
        add("Ambos anotan: Sí", "Resultado", bt, "btts", "btts", 0.5, True, lambda x, y: x > 0 and y > 0)
        add("Ambos anotan: No", "Resultado", lambda x: 1 - bt(x), "btts", "btts", 0.5, False, lambda x, y: x == 0 or y == 0)
    for ln in lineas(*cfg["Total"]):
        add(f"Total Over {ln}", "Total", lambda x, ln=ln: x[tot > ln].sum(), "total", "total", ln, True, lambda x, y, ln=ln: x + y > ln)
        add(f"Total Under {ln}", "Total", lambda x, ln=ln: 1 - x[tot > ln].sum(), "total", "total", ln, False, lambda x, y, ln=ln: x + y < ln)
    if met in MAYOR_NUMERO:
        que = NOM[met].lower()
        add(f"Más {que}: {local}", "Mayor número", p1, "gano", "perdio", 0.5, True, lambda x, y: x > y)
        add(f"Más {que}: empate", "Mayor número", px, "empato", "empato", 0.5, True, lambda x, y: x == y)
        add(f"Más {que}: {visitante}", "Mayor número", p2, "perdio", "gano", 0.5, True, lambda x, y: x < y)
    for ln in lineas(*cfg[local]):
        add1(f"{local} Over {ln}", local, lam_l, ll, lh, ln, True, "a_favor", "en_contra", lambda x, y, ln=ln: x > ln)
        add1(f"{local} Under {ln}", local, lam_l, ll, lh, ln, False, "a_favor", "en_contra", lambda x, y, ln=ln: x < ln)
    for ln in lineas(*cfg[visitante]):
        add1(f"{visitante} Over {ln}", visitante, lam_v, vl, vh, ln, True, "en_contra", "a_favor", lambda x, y, ln=ln: y > ln)
        add1(f"{visitante} Under {ln}", visitante, lam_v, vl, vh, ln, False, "en_contra", "a_favor", lambda x, y, ln=ln: y < ln)
    return out


# ================================================================== analisis de un partido
def analizar_partido(df: pd.DataFrame, local: str, visitante: str, met: str, inc: pd.DataFrame, cfg: dict = None) -> dict:
    """Todo lo que el modelo dice de un partido en una metrica: lambdas con su rango 80%, varianza de cada equipo vs liga,
    medias de la liga, lineas (cfg) y la lista de mercados con prob / pesimista / optimista. inc = incertidumbre(df, met)."""
    r = mo.analizar(df, local, visitante, met, inc=inc)
    lam_l, lam_v = r["lambda_local"], r["lambda_visitante"]
    (ll, lh), (vl, vh) = r["rango"]["lam_l"], r["rango"]["lam_v"]
    if cfg is None:
        cfg = cfg_defecto(lam_l, lam_v, met, local, visitante)
    lst = mercados(r, met, local, visitante, cfg)

    def var(eq, cond):
        return {"equipo": eq, "condicion": cond, "estado": str(inc.loc[eq, f"estado_{cond}"]),
                "ratio": float(inc.loc[eq, f"ratio_{cond}"]), "n_ef": float(inc.loc[eq, f"n_ef_{cond}"])}
    v = {"local": var(local, "casa"), "visitante": var(visitante, "fuera")}
    return {"metrica": met, "nombre": NOM[met], "local": local, "visitante": visitante,
            "lambda_local": lam_l, "lambda_visitante": lam_v,
            "rango": {"local": [ll, lh], "visitante": [vl, vh], "total": [ll + vl, lh + vh]},
            "var": v, "vol": {local: v["local"]["estado"] == "volátil", visitante: v["visitante"]["estado"] == "volátil"},
            "medias_liga": {k: float(x) for k, x in mo.medias_liga(df, met).items()},
            "cfg": cfg, "grupos": list(dict.fromkeys(x["grupo"] for x in lst)), "mercados": lst, "matriz": r["matriz"]}


def ev_pata(mk: dict, cuota: float) -> dict:
    """EV con la cuota de la casa: Poisson y pesimista. EV = prob × cuota − 1."""
    return {"ev": mk["prob"] * cuota - 1, "ev_lo": mk["lo"] * cuota - 1, "justa": mo.cuota_justa(mk["prob"])}


def pata(partido: str, met: str, mk: dict, e: dict, cuota: float) -> dict:
    """Lo que se guarda en el boleto al agregar un mercado."""
    return {"partido": partido, "metrica": NOM[met], "mercado": mk["mercado"], "prob": mk["prob"], "cuota": cuota,
            "cal": e["tag"], "cls": e["cls"], "lo": mk["lo"], "hi": mk["hi"]}


# ================================================================== graficos del modelo ("Que dice el modelo")
def matriz_datos(m: np.ndarray, region, k: int = 6) -> dict:
    """Marcadores exactos (filas = local, columnas = visitante): probabilidad y si con ese marcador gana la pata."""
    return {"k": k, "max": float(m[:k, :k].max()),
            "celdas": [[{"p": float(m[x, y]), "gana": bool(region(x, y))} for y in range(k)] for x in range(k)]}


def distribucion_datos(m: np.ndarray, mk: dict) -> list:
    """Probabilidad de cada cantidad (total del partido o de un equipo) y si con esa cantidad gana la pata."""
    k = m.shape[0]
    if mk["grupo"] == "Total":
        tot = np.add.outer(np.arange(k), np.arange(k))
        dist = np.array([m[tot == s].sum() for s in range(k * 2 - 1)])
    else:
        dist = m.sum(axis=1 if mk["col_l"] == "a_favor" else 0)
    cond = (lambda s: s > mk["linea"]) if mk["over"] else (lambda s: s < mk["linea"])
    hi = len(dist)
    while hi > 1 and dist[hi - 1] < 0.005: hi -= 1
    hi = min(len(dist), max(hi, int(mk["linea"]) + 2))
    return [{"x": s, "p": float(dist[s]), "gana": bool(cond(s))} for s in range(hi)]


def diferencia_datos(m: np.ndarray, mk: dict) -> list:
    """Probabilidad de cada diferencia local - visitante y si con esa diferencia gana la pata."""
    k = m.shape[0]
    dif = np.subtract.outer(np.arange(k), np.arange(k))
    ds = list(range(-(k - 1), k))
    dist = np.array([m[dif == d].sum() for d in ds])
    lo, hi = 0, len(ds)
    while lo < len(ds) - 1 and dist[lo] < 0.005: lo += 1
    while hi > lo + 1 and dist[hi - 1] < 0.005: hi -= 1
    return [{"x": ds[i], "p": float(dist[i]), "gana": bool(mk["region"](max(ds[i], 0), max(-ds[i], 0)))} for i in range(lo, hi)]


def grafico_modelo(m: np.ndarray, mk: dict, met: str) -> dict:
    """Que grafico va con la pata: matriz (goles, Resultado/Total), diferencia (Mayor numero) o distribucion (resto)."""
    if met in GOL and mk["grupo"] in ("Resultado", "Total"):
        return {"tipo": "matriz", **matriz_datos(m, mk["region"])}
    if mk["grupo"] == "Mayor número":
        return {"tipo": "diferencia", "valores": diferencia_datos(m, mk)}
    return {"tipo": "distribucion", "valores": distribucion_datos(m, mk)}


# ================================================================== cara a cara (torneo vigente + anterior)
def cara_a_cara(df: pd.DataFrame, local: str, visitante: str, solo_casa: bool = False) -> dict:
    """Enfrentamientos directos en los dos ultimos torneos: record y la ficha (9 metricas) de cada partido, reciente -> antiguo.
    G/E/P son desde el punto de vista de `local`. Valor None = dato vacio en la base."""
    temps = torneos_recientes(df)
    par = df[df.temporada_txt.isin(temps) & (((df.equipo_local_txt == local) & (df.equipo_visitante_txt == visitante)) |
                                             ((df.equipo_local_txt == visitante) & (df.equipo_visitante_txt == local)))].sort_values("fecha", ascending=False)
    if solo_casa:
        par = par[par.equipo_local_txt == local]
    es_a = par.equipo_local_txt == local
    ga = np.where(es_a, par.goles_local_val, par.goles_visitante_val)
    gb = np.where(es_a, par.goles_visitante_val, par.goles_local_val)
    iv = lambda x: None if pd.isna(x) else int(x)
    partidos = []
    for _, g in par.iterrows():
        gl, gv = iv(g.goles_local_val), iv(g.goles_visitante_val)
        a_, b_ = (gl, gv) if g.equipo_local_txt == local else (gv, gl)
        partidos.append({"fecha": g.fecha, "temporada": g.temporada_txt, "local": g.equipo_local_txt, "visitante": g.equipo_visitante_txt,
                         "goles_local": gl, "goles_visitante": gv,
                         "resultado": None if a_ is None or b_ is None else ("g" if a_ > b_ else ("p" if a_ < b_ else "e")),
                         "metricas": {met: {"local": iv(g[col_l]), "visitante": iv(g[col_v])} for met, (col_l, col_v, _) in mo.METRICAS.items()}})
    return {"local": local, "visitante": visitante, "torneos": temps, "solo_casa": solo_casa, "n": len(par),
            "G": int((ga > gb).sum()), "E": int((ga == gb).sum()), "P": int((ga < gb).sum()), "partidos": partidos}


# ================================================================== boleto y stake
def resumen_boleto(legs: list) -> dict:
    """Probabilidad, cuota y EV del boleto (o None si esta vacio).
    Pesimista / optimista = producto de la prob. pesimista / optimista de cada pata."""
    if not legs:
        return None
    prob = float(np.prod([l["prob"] for l in legs])); cuota = float(np.prod([l["cuota"] for l in legs]))
    lo = float(np.prod([l.get("lo", l["prob"]) for l in legs])); hi = float(np.prod([l.get("hi", l["prob"]) for l in legs]))
    return {"n": len(legs), "prob": prob, "cuota": cuota, "ev": prob * cuota - 1, "lo": lo, "hi": hi,
            "ev_lo": lo * cuota - 1, "ev_hi": hi * cuota - 1, "justa": mo.cuota_justa(prob),
            "mismo_partido": len({l["partido"] for l in legs}) < len(legs)}


def stake(legs: list, banca: float) -> dict:
    """Kelly con la probabilidad pesimista del boleto: si aun asi hay valor, la apuesta aguanta un modelo optimista.
    opciones = Kelly, ½, ¼ y ⅛ con fraccion de banca y monto."""
    rb = resumen_boleto(legs)
    if not rb:
        return None
    f = kelly(rb["lo"], rb["cuota"])
    return {"kelly": f, "sin_valor": f <= 0, "banca": banca, "boleto": rb,
            "opciones": [{"nombre": nm, "fraccion": f / d, "monto": banca * f / d} for nm, d in (("Kelly", 1), ("½ Kelly", 2), ("¼ Kelly", 4), ("⅛ Kelly", 8))]}


# ================================================================== vistas: el paquete completo que necesita cada pantalla
def vista_inicio(df: pd.DataFrame, liga: str, met_tendencias: str = "corners", legs: list = None) -> dict:
    res = resumen_liga(df)
    val = validacion()
    return {"liga": liga, "nombre": LIGAS.get(liga, liga), **res, "validacion": (val or {}).get("ligas", {}).get(liga),
            "medias": medias_por_metrica(df), "tabla": tabla_posiciones(df, res["temporada"]),
            "tendencias": tendencias(df, met_tendencias), "boleto": resumen_boleto(legs or [])}


def vista_tabla(df: pd.DataFrame, liga: str, temp: str = None) -> dict:
    temp = temp or temporada_actual(df)
    return {"liga": liga, "nombre": LIGAS.get(liga, liga), "temporada": temp, "temporadas": temporadas(df), "tabla": tabla_posiciones(df, temp)}


def vista_cara(df: pd.DataFrame, liga: str, local: str, visitante: str, solo_casa: bool = False, legs: list = None) -> dict:
    cc = cara_a_cara(df, local, visitante, solo_casa)
    return {"liga": liga, "nombre": LIGAS.get(liga, liga), **cc, "contexto_ia": contexto_cara(LIGAS.get(liga, liga), cc, legs or [])}


def vista_partido(df: pd.DataFrame, liga: str, local: str, visitante: str, met: str, inc: pd.DataFrame = None, cfg: dict = None,
                  n: int = 5, filtro: str = "Todos", sel: str = None, legs: list = None) -> dict:
    """Armar + Analizar en un solo paquete: mercados de todos los grupos ya evaluados con los ultimos n partidos
    (filtro "Como jugarán" = local en casa / visitante fuera) y el detalle de la pata `sel` (grafico del modelo,
    historial y estadisticas de cada equipo)."""
    inc = incertidumbre(df, met) if inc is None else inc
    an = analizar_partido(df, local, visitante, met, inc, cfg)
    nombre_liga = LIGAS.get(liga, liga); partido = f"{local} vs {visitante} ({nombre_liga})"
    cond_l, cond_v = ("Casa", "Fuera") if filtro != "Todos" else (None, None)
    hl, hv = historial(df, local, met, n, cond_l), historial(df, visitante, met, n, cond_v)
    evaluados = [{**mk, **evaluar(mk, hl, hv, an["vol"])} for mk in an["mercados"]]
    nombres = [x["mercado"] for x in evaluados]
    sel = sel if sel in nombres else nombres[0]
    mk = next(x for x in evaluados if x["mercado"] == sel)
    detalle = {**mk, "grafico": grafico_modelo(an["matriz"], mk, met),
               "historial_local": historial_json(hl), "historial_visitante": historial_json(hv),
               "stats_local": stats_historial(hl, mk["linea"], mk["over"]), "stats_visitante": stats_historial(hv, mk["linea"], mk["over"])}
    base = {k: v for k, v in an.items() if k not in ("mercados", "matriz")}
    return {"liga": liga, "nombre_liga": nombre_liga, "partido": partido, **base, "n": n, "filtro": filtro, "mercados": evaluados, "pata": detalle,
            "boleto": resumen_boleto(legs or []),
            "contexto_armar": contexto_armar(nombre_liga, partido, an, n, mk["grupo"], [(x, x) for x in evaluados if x["grupo"] == mk["grupo"]], legs or []),
            "contexto_analizar": contexto_analizar(nombre_liga, partido, an, sel, mk, mk, n, filtro, hl, hv, legs or [])}


# ================================================================== contexto para el analista IA (texto con los datos de la vista)
def contexto_boleto(legs: list, con_metrica: bool = False) -> str:
    if not legs:
        return "\nBoleto vacío."
    if con_metrica:
        return "\nBoleto actual: " + "; ".join(f"{l['mercado']} ({l['partido']}, {l['metrica']}, modelo {l['prob']:.0%}, cuota casa {l['cuota']})" for l in legs)
    return "\nBoleto actual: " + "; ".join(f"{l['mercado']} ({l['partido']}, modelo {l['prob']:.0%}, cuota {l['cuota']})" for l in legs)


def contexto_inicio(nombre_liga: str, temp: str, ult, medias: list, tabla: list, legs: list) -> str:
    medias_ia = "; ".join(f"{NOM[m['metrica']]} local {m['local']:.2f} visita {m['visitante']:.2f} total {m['total']:.2f}" for m in medias)
    return (f"Vista: Inicio. Liga {nombre_liga}. Temporada {temp}, datos al {ult:%d/%m/%Y}. Medias de liga por partido: {medias_ia}. Tabla: " +
            "; ".join(f"{i + 1}. {f['equipo']} {f['PTS']} pts (J{f['J']} G{f['G']} E{f['E']} P{f['P']}, DG {f['DG']:+d})" for i, f in enumerate(tabla)) +
            contexto_boleto(legs))


def contexto_cara(nombre_liga: str, cc: dict, legs: list) -> str:
    local, visitante, n = cc["local"], cc["visitante"], cc["n"]
    iv = lambda x: "?" if x is None else x
    mv = lambda g, met: f"{iv(g['metricas'][met]['local'])}-{iv(g['metricas'][met]['visitante'])}"
    return (f"Vista: Cara a cara. Liga {nombre_liga}. {local} vs {visitante}, solo {' y '.join(cc['torneos'])}" + (f", solo con {local} en casa" if cc["solo_casa"] else "") +
            f". Récord: {local} {cc['G']} victorias, {cc['E']} empates, {visitante} {cc['P']} victorias en {n} partidos. "
            + (("Partidos (reciente→antiguo): " +
                "; ".join(f"{g['fecha']:%d/%m/%y} {g['local']} {iv(g['goles_local'])}-{iv(g['goles_visitante'])} {g['visitante']} "
                          f"(tiros {mv(g, 'tiros')}, corners {mv(g, 'corners')}, faltas {mv(g, 'faltas')}, amarillas {mv(g, 'amarillas')})"
                          for g in cc["partidos"])) if n else "Sin partidos.")
            + contexto_boleto(legs))


def contexto_armar(nombre_liga: str, partido: str, an: dict, n: int, grp: str, evaluados: list, legs: list) -> str:
    """evaluados = lista de (mercado, evaluacion) del grupo grp."""
    local, visitante, met, ml = an["local"], an["visitante"], an["metrica"], an["medias_liga"]
    vl_, vv_ = an["var"]["local"], an["var"]["visitante"]
    (ll, lh), (vl, vh), (tl, th) = an["rango"]["local"], an["rango"]["visitante"], an["rango"]["total"]
    return (f"Vista: Armar. Liga {nombre_liga}. Partido {partido}. Métrica {NOM[met]}. λ local {an['lambda_local']:.2f} (rango bajo-alto {ll:.2f}-{lh:.2f}, "
            f"varianza {vl_['estado']} {vl_['ratio']:.1f}x la liga, {vl_['n_ef']:.0f} partidos efectivos en casa), "
            f"λ visitante {an['lambda_visitante']:.2f} ({vl:.2f}-{vh:.2f}, {vv_['estado']} {vv_['ratio']:.1f}x, {vv_['n_ef']:.0f} fuera), "
            f"λ total {an['lambda_local'] + an['lambda_visitante']:.2f} ({tl:.2f}-{th:.2f}); media liga local {ml['local']:.2f}, visita {ml['visitante']:.2f}, total {ml['total']:.2f}. "
            f"El rango es el intervalo del 80% del promedio del equipo (t de Student, desv/raíz(n)): incertidumbre de la λ, no la varianza Poisson. "
            f"Validación con últimos {n} partidos.\n"
            "Mercados del grupo " + grp + ":\n" + "\n".join(
                f"- {mk['mercado']}: prob Poisson {mk['prob']:.0%} (pesimista {mk['lo']:.0%}, optimista {mk['hi']:.0%})"
                f", cuota justa {mo.cuota_justa(mk['prob'])}, {local} cumplió {ev_['hl']}/{ev_['nl']}, {visitante} {ev_['hv']}/{ev_['nv']}, "
                f"calificación {ev_['tag']}"
                for mk, ev_ in evaluados) + contexto_boleto(legs, con_metrica=True))


def contexto_analizar(nombre_liga: str, partido: str, an: dict, sel: str, mk: dict, e: dict, n: int, filtro: str,
                      hl: pd.DataFrame, hv: pd.DataFrame, legs: list) -> str:
    local, visitante, met, ml = an["local"], an["visitante"], an["metrica"], an["medias_liga"]
    vl_, vv_ = an["var"]["local"], an["var"]["visitante"]
    (ll, lh), (vl, vh) = an["rango"]["local"], an["rango"]["visitante"]

    def _st(h):
        return (f"a favor media {h.a_favor.mean():.1f} mediana {h.a_favor.median():.1f} desv {h.a_favor.std(ddof=0):.1f}; "
                f"en contra media {h.en_contra.mean():.1f}; total media {h.total.mean():.1f} máx {h.total.max()} mín {h.total.min()}") if len(h) else "sin partidos"

    def _res(h):
        return ", ".join(f"{r_.condicion[0]} vs {r_.rival} {r_.marcador} ({int(r_.a_favor)}-{int(r_.en_contra)} {NOM[met].lower()})" for _, r_ in h.iterrows())
    return (f"Vista: Analizar. Liga {nombre_liga}. Partido {partido}. Métrica {NOM[met]}. Pata: {sel}. Prob modelo (Poisson) {mk['prob']:.0%} "
            f"(pesimista {mk['lo']:.0%}, optimista {mk['hi']:.0%}; Poisson con la λ del extremo en contra / a favor). "
            f"Varianza vs liga: {local} {vl_['estado']} {vl_['ratio']:.1f}x en casa, {visitante} {vv_['estado']} {vv_['ratio']:.1f}x fuera"
            f", cuota justa {mo.cuota_justa(mk['prob'])}, calificación {e['tag']}, cumplimiento histórico {e['tasa']:.0%} ({e['hl']}/{e['nl']} {local}, {e['hv']}/{e['nv']} {visitante}) "
            f"en últimos {n} partidos, filtro {filtro}. λ {local} {an['lambda_local']:.2f} (rango 80% {ll:.2f}-{lh:.2f}), λ {visitante} {an['lambda_visitante']:.2f} ({vl:.2f}-{vh:.2f}), "
            f"media liga local {ml['local']:.2f} visita {ml['visitante']:.2f} total {ml['total']:.2f}.\n"
            f"{local} últimos {len(hl)}: {_st(hl)}. Resultados (reciente→antiguo): " + _res(hl) +
            f"\n{visitante} últimos {len(hv)}: {_st(hv)}. Resultados: " + _res(hv) + contexto_boleto(legs))


# ================================================================== diccionario (texto fijo de la app)
DICCIONARIO_GRUPOS = {"Modelo": "Cómo se calculan las probabilidades.", "Mercados": "Qué es cada apuesta y cómo leer cuota y EV.",
                      "Validación": "Cómo se comprueba una pata contra el historial y qué significa la calificación.",
                      "Banca": "Cuánto apostar.", "Datos": "De dónde salen los datos y cómo se ordenan."}
DICCIONARIO = [
    ("Modelo", "λ (lambda)", "Cantidad esperada de la métrica para un equipo en este partido, según el modelo. Ej. λ corners 5.2 = se esperan unos 5 corners de ese equipo."),
    ("Modelo", "Poisson", "Fórmula que convierte una λ en probabilidades: cuántas veces sale 0, 1, 2, 3… Se usa para goles, tiros, corners, faltas y tarjetas."),
    ("Modelo", "Dixon-Coles (ρ)", "Corrección a Poisson solo para goles: ajusta los marcadores 0-0, 1-0, 0-1 y 1-1, que Poisson estima mal. ρ negativo = más empates bajos."),
    ("Modelo", "Ataque / defensa", "Fuerza del equipo relativa a la liga. 1.00 = promedio; 1.30 = produce 30% más que un equipo promedio; 0.80 = 20% menos."),
    ("Modelo", "Peso por recencia", "Los partidos recientes pesan más que los viejos al calcular las fuerzas. Un partido de hace ~140 días pesa la mitad que uno de hoy."),
    ("Modelo", "Matriz de resultados", "Tabla con la probabilidad de cada marcador exacto (filas = local, columnas = visitante). Verde = marcadores con los que gana la pata."),
    ("Modelo", "Rango bajo–alto de λ", "Entre paréntesis junto a cada λ: hasta dónde puede estar equivocado el promedio del equipo. Se calcula sobre sus propios partidos (con la misma recencia del modelo): promedio ± t × desviación estándar ÷ √n. El multiplicador t sale de la distribución t de Student y baja solo conforme hay más partidos (3 partidos 1.89, 21 partidos 1.33, muchos 1.28); el rango cubre el 80% de los casos. Mide confianza en la λ, no cuánto varía un partido: eso ya lo cubre Poisson."),
    ("Modelo", "Pesimista / optimista", "La probabilidad del mercado calculada con el mismo Poisson pero con las λ del extremo que va en contra (pesimista) o a favor (optimista) de la pata. Salen de las mismas λ bajo–alto que ves arriba, así que un Over y su Under siempre cuadran. El EV pesimista usa la prob. pesimista: si sigue positivo, la pata aguanta aunque el promedio esté algo inflado."),
    ("Modelo", "Varianza vs liga (🟢🟡🔴⚪)", "Ancho del rango del equipo (relativo a su promedio, en esa condición: casa o fuera) dividido entre el ancho mediano de los equipos de la liga. 🟢 estable < 0.8×, 🟡 normal 0.8–1.2×, 🔴 volátil > 1.2×, ⚪ pocos datos = menos de 5 partidos efectivos en esa condición; ahí se usa la dispersión típica de la liga en lugar de la del equipo."),
    ("Modelo", "Encogimiento (K)", "Al calcular la fuerza de un equipo se le suman 10 partidos 'extra' al promedio de la liga. Así un equipo con pocos partidos o una racha rara no se va a extremos (λ = 0 o λ = 8). El backtest mostró que sin esto el modelo decía 85% y acertaba 79%; con esto dice 85% y acierta 85%."),
    ("Mercados", "Cuota justa", "1 dividido entre la probabilidad Poisson. Es la cuota a la que no ganas ni pierdes a largo plazo. Si la casa paga más que la justa, hay valor."),
    ("Mercados", "EV (valor esperado)", "prob. × cuota − 1. Positivo = a largo plazo ganas; negativo = pierdes. EV +0.10 = ganas 10 centavos por cada Q1 apostado, en promedio."),
    ("Mercados", "Over / Under", "Más de / menos de una línea. Total Over 2.5 goles = 3 o más goles en el partido. Las líneas .5 no permiten empate."),
    ("Mercados", "Línea y ± líneas", "Línea = el centro que quieres ver (ej. 9.5 corners). ± líneas = cuántas líneas alrededor mostrar (±2 con 9.5 muestra 7.5, 8.5, 9.5, 10.5 y 11.5)."),
    ("Mercados", "1X2 / doble oportunidad", "1 = gana local, X = empate, 2 = gana visitante. 1X = local o empate; X2 = visitante o empate."),
    ("Mercados", "Ambos anotan (BTTS)", "Sí = los dos equipos marcan al menos un gol. No = al menos uno se queda en cero."),
    ("Mercados", "Total / Local / Visitante", "Grupos de mercados. Total suma los dos equipos; Local y Visitante son la métrica de un solo equipo."),
    ("Mercados", "Mayor número", "Qué equipo termina con más tiros, tiros a puerta, corners, faltas o amarillas (o empate). Probabilidad = matriz Poisson de la métrica."),
    ("Validación", "Últ. N", "Contra cuántos partidos recientes de cada equipo se valida la pata. N chico = forma actual; N grande = tendencia estable."),
    ("Validación", "X/N cumplió", "En cuántos de los últimos N partidos del equipo se habría cumplido ese mercado. 4/5 = pasó en 4 de 5."),
    ("Validación", "Calificación", "60% probabilidad Poisson + 40% cumplimiento histórico. Excelente ≥ 78%, Buena ≥ 68%, Regular ≥ 56%, Mala ≥ 45%, Pésima el resto."),
    ("Validación", "↕ Equipo volátil", "Un equipo de la pata es 🔴 volátil frente a la liga (el local en casa o el visitante fuera; en Total, Resultado y Mayor número cuentan los dos): la calificación baja un nivel."),
    ("Validación", "Como jugarán", "Filtro: solo partidos del local jugando en casa y del visitante jugando fuera."),
    ("Validación", "Media / mediana / desv. est.", "Media = promedio. Mediana = valor del medio (resiste goleadas raras). Desviación estándar = qué tanto varía de partido a partido; alta = equipo irregular."),
    ("Validación", "Media liga", "Promedio de todos los partidos cargados. Referencia para saber si un equipo está por encima o por debajo de lo normal."),
    ("Validación", "Línea típica y % Over (Inicio)", "Línea .5 más cercana a la media de la liga de esa métrica (ej. 2.5 goles, 9.5 corners). % Over = en qué porcentaje de los partidos cargados el total superó esa línea. Sirve para saber qué tan normal es un Over antes de mirar a los equipos."),
    ("Validación", "Cara a cara", "Enfrentamientos directos entre los dos equipos solo en el torneo vigente y el anterior. Récord y la ficha completa de cada partido (las 9 métricas): la pastilla de color marca al equipo que hizo más. Son pocos partidos (2 o 3): contexto, no prueba."),
    ("Validación", "Tabla de λ", "Una fila por equipo y el total: λ = esperado del modelo, bajo–alto = hasta dónde puede estar equivocado ese promedio, liga = media de la liga en esa condición, Δ = λ menos la media liga, var. = varianza del equipo vs liga (🟢🟡🔴⚪ y ×N)."),
    ("Banca", "Banca", "Dinero total destinado a apostar. Todo el stake se calcula como porcentaje de esto."),
    ("Banca", "Kelly", "Fracción de banca que maximiza el crecimiento si la probabilidad fuera exacta: ((cuota−1)·p − (1−p)) / (cuota−1). Se calcula con la prob. pesimista del boleto (producto de las pesimistas de cada pata): si con esa aún hay valor, el stake aguanta un modelo demasiado optimista."),
    ("Banca", "½, ¼, ⅛ Kelly", "La mitad, un cuarto y un octavo del Kelly completo. Para parlays usa ¼ o ⅛: menos crecimiento pero mucha menos probabilidad de quebrar."),
    ("Banca", "Patas no independientes", "Dos patas del mismo partido (ej. gana Madrid + over 2.5) están relacionadas; multiplicar sus probabilidades da un número inexacto."),
    ("Datos", "Fuente", "football-data.co.uk para las 5 ligas europeas; ESPN para Liga MX. Se descarga todos los días a las 6:00 am (Guatemala) por GitHub Actions."),
    ("Datos", "Columnas _val", "goles, goles 1er/2do tiempo, tiros, tiros a puerta, corners, faltas, amarillas y rojas, cada una para local y visitante."),
    ("Datos", "Jornada", "Estimada: partido n-ésimo de cada equipo en la temporada. Un aplazado se cuenta cuando se jugó."),
    ("Datos", "Temporada", "Europa: formato 2025-26 (agosto a mayo). Liga MX: Clausura AAAA (enero-junio) y Apertura AAAA (julio-diciembre), Liguilla incluida."),
]


def diccionario(q: str = "") -> list:
    """Grupos del diccionario con sus terminos, filtrados por texto (en el termino o la definicion)."""
    q = (q or "").strip().lower()
    out = []
    for g in dict.fromkeys(g for g, _, _ in DICCIONARIO):
        items = [{"termino": t_, "definicion": d_} for gg, t_, d_ in DICCIONARIO if gg == g and (not q or q in t_.lower() or q in d_.lower())]
        if items:
            out.append({"grupo": g, "descripcion": DICCIONARIO_GRUPOS.get(g, ""), "items": items})
    return out


# ================================================================== JSON
def a_json(x):
    """Convierte un resultado a tipos puros de Python: numpy -> float/int/bool, fechas -> 'AAAA-MM-DD', DataFrame -> filas,
    NaN -> None. Quita funciones (region) y claves que empiezan con '_'."""
    if isinstance(x, dict):
        return {str(k): a_json(v) for k, v in x.items() if not (isinstance(k, str) and k.startswith("_")) and not callable(v)}
    if isinstance(x, (list, tuple)):
        return [a_json(v) for v in x]
    if isinstance(x, np.ndarray):
        return a_json(x.tolist())
    if isinstance(x, pd.DataFrame):
        return a_json(x.to_dict("records"))
    if isinstance(x, pd.Series):
        return a_json(x.tolist())
    if isinstance(x, (pd.Timestamp, datetime, date)):
        return x.strftime("%Y-%m-%d")
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return None if math.isnan(x) else float(x)
    return x


# ================================================================== CLI
if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit('Uso: python kuota.py <liga> "Local" "Visitante" [metrica]   ej. python kuota.py laliga "Real Madrid" "Barcelona" corners')
    liga, local, visitante = sys.argv[1:4]
    met = sys.argv[4] if len(sys.argv) > 4 else "goles"
    v = vista_partido(cargar(liga), liga, local, visitante, met)
    print(json.dumps(a_json(v), ensure_ascii=False, indent=1))

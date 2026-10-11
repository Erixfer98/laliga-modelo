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
import probabilidades as pr
from functools import lru_cache
from itertools import product

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
    df = mo.cargar(f"{carpeta}/bbdd_{liga}.csv")
    df.attrs["liga"] = liga
    return df


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


def kelly(p: float, cuota: float, push: float = 0.0) -> float:
    """Kelly individual con acierto, fallo y devolución; nunca recomienda fracción negativa."""
    if not all(math.isfinite(x) for x in (p, cuota, push)) or cuota <= 1:
        raise ValueError("probabilidades y cuota deben ser finitas; cuota > 1")
    if p < 0 or push < 0 or p + push > 1 + 1e-12:
        raise ValueError("probabilidades de liquidación inválidas")
    return pr.kelly({cuota: p, 1.0: push, 0.0: max(0., 1-p-push)})


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
            "push_l": int((hl[mk["col_l"]] == mk["linea"]).sum()) if mk["regla"]["tipo"] == "ou" else 0,
            "push_v": int((hv[mk["col_v"]] == mk["linea"]).sum()) if mk["regla"]["tipo"] == "ou" else 0,
            "serie_push_l": [bool(x) for x in ((hl[mk["col_l"]] == mk["linea"]) if mk["regla"]["tipo"] == "ou" else pd.Series(False, index=hl.index))],
            "serie_push_v": [bool(x) for x in ((hv[mk["col_v"]] == mk["linea"]) if mk["regla"]["tipo"] == "ou" else pd.Series(False, index=hv.index))],
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
    return [x for x in np.arange(centro - rango, centro + rango + 0.01, 1.0) if x >= 0]


def centro_defecto(lam: float, met: str) -> float:
    if met == "goles": return 2.5
    if met in GOL: return 1.5
    if met == "rojas": return 0.5
    return max(round(lam) - 0.5, 0.5)


def cfg_defecto(lam_l: float, lam_v: float, met: str, local: str, visitante: str) -> dict:
    """Lineas iniciales por grupo: {grupo: [centro, ± lineas]}."""
    return {"Total": [centro_defecto(lam_l + lam_v, met), 2 if met == "goles" else 1],
            local: [centro_defecto(lam_l, met), 1], visitante: [centro_defecto(lam_v, met), 1]}


def mercados(r: dict, met: str, local: str, visitante: str, cfg: dict, _memo=None) -> list:
    """Mercados y liquidaciones en el mismo soporte. Lo/hi son extremos de la
    rejilla de sensibilidad que incluye el centro, sin cobertura validada."""
    m = r["matriz"]
    muestras = r["rango"]["esquinas"].values()
    out = []

    def add(nombre, grupo, col_l, col_v, linea, over, regla):
        def calcular():
            win, push = pr.liquidacion(regla, m.shape[0]-1)
            ps = [pr.prob_evento(e, win) for e in muestras]
            pushes = [pr.prob_evento(e, push) for e in muestras]
            p, pp = pr.prob_evento(m, win), pr.prob_evento(m, push)
            return {"mercado": nombre, "grupo": grupo, "prob": p, "push": pp, "loss": max(0., 1-p-pp),
                        "lo": min(ps), "hi": max(ps), "push_lo": min(pushes), "push_hi": max(pushes),
                        "justa": mo.cuota_justa(p, pp), "regla": regla,
                        "escenarios": [{"prob": pw, "push": pu} for pw, pu in zip(ps, pushes)],
                        "col_l": col_l, "col_v": col_v, "linea": linea, "over": over,
                        "region": lambda x, y, win=win: bool(win[x, y]), "_mascara": win}
        out.append(dict(_memo(regla, calcular) if _memo else calcular()))

    def resultado(nombre, grupo, col_l, col_v, lado):
        add(nombre, grupo, col_l, col_v, .5, True, {"tipo": "resultado", "lado": lado})

    if met in GOL:
        resultado(f"Gana {local}", "Resultado", "gano", "perdio", "local")
        resultado("Empate", "Resultado", "empato", "empato", "empate")
        resultado(f"Gana {visitante}", "Resultado", "perdio", "gano", "visitante")
        resultado(f"{local} o empate", "Resultado", "no_perdio", "no_gano", "local_empate")
        resultado(f"{visitante} o empate", "Resultado", "no_gano", "no_perdio", "visitante_empate")
        for si in (True, False):
            add("Ambos anotan: " + ("Sí" if si else "No"), "Resultado", "btts", "btts", .5, si,
                {"tipo": "btts", "si": si})
    if met in MAYOR_NUMERO:
        que = NOM[met].lower()
        resultado(f"Más {que}: {local}", "Mayor número", "gano", "perdio", "local")
        resultado(f"Más {que}: empate", "Mayor número", "empato", "empato", "empate")
        resultado(f"Más {que}: {visitante}", "Mayor número", "perdio", "gano", "visitante")
    for grupo, lado, col_l, col_v in (("Total", "total", "total", "total"),
                                     (local, "local", "a_favor", "en_contra"),
                                     (visitante, "visitante", "en_contra", "a_favor")):
        for ln in lineas(*cfg[grupo]):
            for over in (True, False):
                add(f"{grupo} {'Over' if over else 'Under'} {ln}", grupo, col_l, col_v, ln, over,
                    {"tipo": "ou", "lado": lado, "linea": float(ln), "over": over})
    orden = {"Resultado": 0, "Total": 1, "Mayor número": 2, local: 3, visitante: 4}
    return sorted(out, key=lambda mk: orden[mk["grupo"]])


# ================================================================== analisis de un partido
def analizar_partido(df: pd.DataFrame, local: str, visitante: str, met: str, inc: pd.DataFrame, cfg: dict = None, _modelo: dict = None, _memo=None) -> dict:
    """Todo lo que el modelo dice de un partido en una metrica: lambdas con su rango heurístico, varianza de cada equipo vs liga,
    medias de la liga, lineas (cfg) y la lista de mercados con prob / pesimista / optimista. inc = incertidumbre(df, met)."""
    r = mo.analizar(df, local, visitante, met, inc=inc) if _modelo is None else _modelo
    lam_l, lam_v = r["lambda_local"], r["lambda_visitante"]
    (ll, lh), (vl, vh) = r["rango"]["lam_l"], r["rango"]["lam_v"]
    if cfg is None:
        cfg = cfg_defecto(lam_l, lam_v, met, local, visitante)
    if set(cfg) != {"Total", local, visitante}:
        raise ValueError("cfg debe incluir Total y ambos equipos")
    if any(not isinstance(v, (list, tuple)) or len(v) != 2 for v in cfg.values()):
        raise ValueError("cada cfg requiere [centro, amplitud]")
    for centro, amplitud in cfg.values():
        try:
            pr.validar_linea(float(centro))
        except (ValueError, TypeError) as exc:
            raise ValueError("centro de línea inválido") from exc
        if not isinstance(amplitud, (int, float)) or not float(amplitud).is_integer() or not 0 <= amplitud <= 10:
            raise ValueError("amplitud de líneas debe ser un entero entre 0 y 10")
    cfg = {key: [float(value[0]), int(value[1])] for key, value in cfg.items()}
    lst = mercados(r, met, local, visitante, cfg, _memo=_memo)
    for mk in lst:
        mk["seleccion"] = {"liga": df.attrs.get("liga"), "local": local, "visitante": visitante,
                           "metrica": met, "regla": mk["regla"], "version": pr.VERSION}


    def var(eq, cond):
        return {"equipo": eq, "condicion": cond, "estado": str(inc.loc[eq, f"estado_{cond}"]),
                "ratio": float(inc.loc[eq, f"ratio_{cond}"]), "n_ef": float(inc.loc[eq, f"n_ef_{cond}"])}
    v = {"local": var(local, "casa"), "visitante": var(visitante, "fuera")}
    return {"metrica": met, "nombre": NOM[met], "local": local, "visitante": visitante,
            "lambda_local": lam_l, "lambda_visitante": lam_v,
            "rango": {"local": [ll, lh], "visitante": [vl, vh], "total": [ll + vl, lh + vh]},
            "distribucion": r["distribucion"], "sensibilidad": {key: val for key, val in r["rango"].items() if key != "esquinas"},
            "var": v, "vol": {local: v["local"]["estado"] == "volátil", visitante: v["visitante"]["estado"] == "volátil"},
            "medias_liga": {k: float(x) for k, x in mo.medias_liga(df, met).items()},
            "cfg": cfg, "grupos": list(dict.fromkeys(x["grupo"] for x in lst)), "mercados": lst, "matriz": r["matriz"]}


def ev_pata(mk: dict, cuota: float) -> dict:
    """EV = acierto × cuota + devolución − 1; mínimo de escenarios pareados."""
    if not math.isfinite(cuota) or cuota <= 1:
        raise ValueError("cuota debe ser finita y mayor que 1")
    escenarios = mk.get("escenarios", [{"prob": mk["lo"], "push": mk.get("push", 0)}])
    return {"ev": mk["prob"] * cuota + mk.get("push", 0) - 1,
            "ev_lo": min(e["prob"] * cuota + e["push"] - 1 for e in escenarios),
            "justa": mo.cuota_justa(mk["prob"], mk.get("push", 0))}


def pata(partido: str, met: str, mk: dict, e: dict, cuota: float) -> dict:
    """Lo que se guarda en el boleto al agregar un mercado."""
    return {"partido": partido, "metrica": NOM[met], "mercado": mk["mercado"], "prob": mk["prob"], "cuota": cuota,
            "cal": e["tag"], "cls": e["cls"], "lo": mk["lo"], "hi": mk["hi"],
            "push": mk["push"], "justa": mk["justa"], "seleccion": mk["seleccion"]}


# ================================================================== graficos del modelo ("Que dice el modelo")
def matriz_datos(m: np.ndarray, region, k: int = 6, regla: dict = None) -> dict:
    """Marcadores exactos (filas = local, columnas = visitante): probabilidad y si con ese marcador gana la pata."""
    k = min(k, m.shape[0])
    push = pr.liquidacion(regla, m.shape[0]-1)[1] if regla else np.zeros(m.shape, dtype=bool)
    return {"masa_visible": float(m[:k, :k].sum()), "k": k, "max": float(m[:k, :k].max()),
            "celdas": [[{"p": float(m[x, y]), "gana": bool(region(x, y)), "push": bool(push[x, y])} for y in range(k)] for x in range(k)]}


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
    return [{"x": s, "p": float(dist[s]), "gana": bool(cond(s)), "push": bool(s == mk["linea"])} for s in range(hi)]


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
        return {"tipo": "matriz", **matriz_datos(m, mk["region"], regla=mk["regla"])}
    if mk["grupo"] == "Mayor número":
        vals = diferencia_datos(m, mk)
        return {"tipo": "diferencia", "valores": vals, "masa_visible": sum(v["p"] for v in vals)}
    vals = distribucion_datos(m, mk)
    return {"tipo": "distribucion", "valores": vals, "masa_visible": sum(v["p"] for v in vals)}


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
@lru_cache(maxsize=8)
def _modelo_boleto(liga, local, visitante, met, mtime):
    df = cargar(liga)
    if local == visitante or local not in equipos(df) or visitante not in equipos(df):
        raise ValueError("equipos inválidos")
    return mo.analizar(df, local, visitante, met, inc=incertidumbre(df, met))


def resumen_boleto(legs: list) -> dict:
    """Recalcula desde identidades de selección; nunca confía en probabilidades del cliente.

    Mismo partido y métrica: intersección y liquidación en una matriz compartida.
    Métricas distintas: no hay distribución conjunta. Partidos distintos:
    independencia explícita (hipótesis no validada). Las cuotas se multiplican:
    no incorpora reglas especiales/precios de una casa para same-game parlays.
    """
    if not legs:
        return None
    if len(legs) > 12:
        raise ValueError("máximo 12 selecciones")
    try:
        cuotas = [float(l["cuota"]) for l in legs]
    except (TypeError, KeyError, ValueError) as exc:
        raise ValueError("cuota inválida") from exc
    if any(not math.isfinite(c) or c <= 1 or c > 10000 for c in cuotas):
        raise ValueError("cuotas deben estar entre 1 (excluido) y 10000")
    cuota = math.prod(cuotas)
    rb = {"n": len(legs), "cuota": cuota, "prob": None, "lo": None, "hi": None,
          "ev": None, "ev_lo": None, "ev_hi": None, "justa": None,
          "mismo_partido": False, "disponible": False, "kelly": None, "advertencias": [],
          "metodo_rango": "sensibilidad heurística, cobertura no validada", "modelos": []}
    def unavailable(motivo, estado):
        rb.update(estado=estado, advertencias=[motivo])
        return rb
    groups, games, seen = {}, {}, set()
    for leg, c in zip(legs, cuotas):
        sel = leg.get("seleccion")
        if not isinstance(sel, dict) or sel.get("version") != pr.VERSION or not sel.get("liga"):
            return unavailable("Selección antigua o sin identidad verificable: vuelve a agregarla.", "sin_modelo")
        liga, local, vis, met = (sel.get(key) for key in ("liga", "local", "visitante", "metrica"))
        if not all(isinstance(x, str) for x in (liga, local, vis, met)):
            raise ValueError("identidad de selección inválida")
        if liga not in LIGAS or met not in mo.METRICAS:
            raise ValueError("liga o métrica no implementada")
        regla = pr.validar_regla(sel.get("regla"))
        if not isinstance(regla, dict):
            raise ValueError("regla de liquidación requerida")
        # Validar antes de acceder a datos o reservar matrices.
        try:
            pr.liquidacion(regla, 6)
        except (KeyError, TypeError) as exc:
            raise ValueError("regla de liquidación inválida") from exc
        game = (liga, local, vis)
        key = (*game, met)
        ident = (*key, json.dumps(regla, sort_keys=True))
        if ident in seen:
            return unavailable("Selecciones duplicadas: elimina la repetida.", "duplicado")
        seen.add(ident)
        groups.setdefault(key, []).append((regla, c))
        games.setdefault(game, set()).add(met)
    rb["mismo_partido"] = len(games) < len(legs)
    if rb["mismo_partido"]:
        rb["advertencias"].append("EV y Kelly suponen producto de cuotas ganadoras y eliminación de pushes. No aplican si la casa usa otro precio o liquidación para la combinada del mismo partido.")
    if any(len(mets) > 1 for mets in games.values()):
        return unavailable("Métricas distintas del mismo partido: no existe distribución conjunta válida.", "sin_modelo")
    if len(games) > 1:
        rb["advertencias"].append("Se asume independencia entre partidos distintos; no está validada empíricamente.")
    central, candidates, probs, lows, highs = [], [], [], [], []
    max_retornos = []
    for key, sels in groups.items():
        liga, local, vis, met = key
        ruta = f"{CARPETA_DATOS}/bbdd_{liga}.csv"
        mtime = os.path.getmtime(ruta)
        r = _modelo_boleto(*key, mtime)
        rb["modelos"].append({"liga": liga, "local": local, "visitante": vis, "metrica": met,
                              "revision_csv_mtime": mtime, "lambda_local": r["lambda_local"],
                              "lambda_visitante": r["lambda_visitante"], "distribucion": r["distribucion"],
                              "rango_local": r["rango"]["lam_l"], "rango_visitante": r["rango"]["lam_v"]})
        reglas, odds = zip(*sels)
        dist, prob = pr.retornos(r["matriz"], reglas, odds)
        acierto_posible, max_retorno = pr.compatibilidad(reglas, odds)
        max_retornos.append(max_retorno)
        if not acierto_posible and max_retorno > 0:
            rb["advertencias"].append("Sin acierto total posible en un grupo; se conservan los retornos parciales por devoluciones.")
        cs = [pr.retornos(m, reglas, odds) for m in r["rango"]["esquinas"].values()]
        central.append(dist); candidates.append([d for d, _ in cs]); probs.append(prob)
        lows.append(min(p for _, p in cs)); highs.append(max(p for _, p in cs))
    combined = pr.combinar(central)
    rb.update(disponible=True, estado="calculado", prob=math.prod(probs), lo=math.prod(lows), hi=math.prod(highs),
              ev=pr.ev(combined), push=combined.get(1.0, 0.0),
              liquidaciones=[{"retorno": r, "prob": p} for r, p in sorted(combined.items())])
    # Un boleto sin pushes tiene dos retornos: 0 o cuota total.
    binary = all(all(ret in (0., math.prod(c for _, c in groups[key])) for ret in d)
                 for key, cs in zip(groups, candidates) for d in cs)
    if binary:
        rb.update(ev_lo=rb["lo"]*cuota-1, ev_hi=rb["hi"]*cuota-1,
                  kelly=pr.kelly({cuota: rb["lo"], 0.: 1-rb["lo"]}), justa=mo.cuota_justa(rb["prob"]))
    elif math.prod(len(cs) for cs in candidates) <= 4096:
        ds = [pr.combinar(ds) for ds in product(*candidates)]
        rb.update(ev_lo=min(pr.ev(d) for d in ds), ev_hi=max(pr.ev(d) for d in ds),
                  kelly=min(pr.kelly(d) for d in ds))
        if len(legs) == 1:
            rb["justa"] = mo.cuota_justa(rb["prob"], rb["push"])
        else:
            rb["advertencias"].append("Cuota justa única no disponible para un boleto con retornos parciales por devoluciones.")
    else:
        rb["advertencias"].append("Kelly y extremos de EV no disponibles: demasiados escenarios de devolución.")
    if len(legs) > 1 and math.prod(max_retornos) <= 1:
        rb.update(estado="incompatible", kelly=None)
        rb["advertencias"].append("Selecciones incompatibles: ningún retorno con beneficio es posible; stake deshabilitado.")
    rb["advertencias"].append("Rangos y Kelly de sensibilidad son heurísticos; no garantizan cobertura ni rentabilidad.")
    return rb


def stake(legs: list, banca: float) -> dict:
    if not math.isfinite(banca) or banca <= 0:
        raise ValueError("banca debe ser finita y positiva")
    rb = resumen_boleto(legs)
    return stake_desde_resumen(rb, banca)


def stake_desde_resumen(rb, banca):
    if rb is None:
        return None
    if not math.isfinite(banca) or banca <= 0:
        raise ValueError("banca debe ser finita y positiva")
    f = rb["kelly"]
    return {"kelly": f, "disponible": f is not None, "sin_valor": f is not None and f <= 0,
            "banca": banca, "boleto": rb, "advertencia": " ".join(rb["advertencias"]),
            "opciones": [] if f is None or f <= 0 else [
                {"nombre": nm, "fraccion": f/d, "monto": banca*f/d}
                for nm, d in (("Kelly", 1), ("½ Kelly", 2), ("¼ Kelly", 4), ("⅛ Kelly", 8))]}


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


def preparar_partido(df, local, visitante, met, inc, cfg=None, n=5, filtro="Todos", _modelo=None, _memo=None):
    """Estado reutilizable. Los consumidores no deben mutar los objetos compartidos."""
    inc = incertidumbre(df, met) if inc is None else inc
    an = analizar_partido(df, local, visitante, met, inc, cfg, _modelo=_modelo, _memo=_memo)
    cond_l, cond_v = ("Casa", "Fuera") if filtro != "Todos" else (None, None)
    hl, hv = historial(df, local, met, n, cond_l), historial(df, visitante, met, n, cond_v)
    evaluados = [{**mk, **evaluar(mk, hl, hv, an["vol"])} for mk in an["mercados"]]
    return an, hl, hv, evaluados


def vista_partido(df: pd.DataFrame, liga: str, local: str, visitante: str, met: str, inc: pd.DataFrame = None, cfg: dict = None,
                  n: int = 5, filtro: str = "Todos", sel: str = None, legs: list = None, grupo: str = None, _preparado=None, modo="completo") -> dict:
    """Armar + Analizar en un solo paquete: mercados de todos los grupos ya evaluados con los ultimos n partidos
    (filtro "Como jugarán" = local en casa / visitante fuera) y el detalle de la pata `sel` (grafico del modelo,
    historial y estadisticas de cada equipo). Si `sel` no existe, se toma el primer mercado del `grupo` (o el primero de todos)."""
    an, hl, hv, evaluados = preparar_partido(df, local, visitante, met, inc, cfg, n, filtro) if _preparado is None else _preparado
    nombre_liga = LIGAS.get(liga, liga); partido = f"{local} vs {visitante} ({nombre_liga})"
    base = {k: v for k, v in an.items() if k not in ("mercados", "matriz")}
    if modo == "resumen":
        return {"liga": liga, "nombre_liga": nombre_liga, "partido": partido, **base,
                "n": n, "filtro": filtro, "mercados": evaluados}
    nombres = [x["mercado"] for x in evaluados]
    if sel not in nombres:
        del_grupo = [x["mercado"] for x in evaluados if x["grupo"] == grupo]
        sel = del_grupo[0] if del_grupo else nombres[0]
    mk = next(x for x in evaluados if x["mercado"] == sel)
    detalle = {**mk, "grafico": grafico_modelo(an["matriz"], mk, met),
               "historial_local": historial_json(hl), "historial_visitante": historial_json(hv),
               "stats_local": stats_historial(hl, mk["linea"], mk["over"]), "stats_visitante": stats_historial(hv, mk["linea"], mk["over"])}
    if modo == "detalle":
        return detalle
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
            f"El rango es sensibilidad heurística de ataque y defensa, sin cobertura validada; la rejilla incluye puntos interiores y el centro. "
            f"Validación con últimos {n} partidos.\n"
            "Mercados del grupo " + grp + ":\n" + "\n".join(
                f"- {mk['mercado']}: prob Poisson {mk['prob']:.0%} (pesimista {mk['lo']:.0%}, optimista {mk['hi']:.0%})"
                f", cuota justa {mk['justa']}, {local} cumplió {ev_['hl']}/{ev_['nl']}, {visitante} {ev_['hv']}/{ev_['nv']}, "
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
            f", cuota justa {mk['justa']}, calificación {e['tag']}, cumplimiento histórico {e['tasa']:.0%} ({e['hl']}/{e['nl']} {local}, {e['hv']}/{e['nv']} {visitante}) "
            f"en últimos {n} partidos, filtro {filtro}. λ {local} {an['lambda_local']:.2f} (rango heurístico {ll:.2f}-{lh:.2f}), λ {visitante} {an['lambda_visitante']:.2f} ({vl:.2f}-{vh:.2f}), "
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
    ("Modelo", "Rango bajo–alto de λ", "Sensibilidad heurística de los promedios ponderados de ataque y defensa, propagada a λ. Se evalúa una rejilla interior y la estimación central. No es un intervalo de confianza validado; no garantiza extremos globales ni cobertura. La referencia de liga permanece fija. Para cero eventos se usa un límite Poisson de cero eventos como sensibilidad."),
    ("Modelo", "Pesimista / optimista", "Mínimo y máximo de la probabilidad en una rejilla de sensibilidad que incluye el punto central. Evalúa ataque y defensa. No garantiza extremos globales ni cobertura. En líneas enteras Over + Under + devolución = 1; el EV usa acierto y devolución de cada mismo escenario."),
    ("Modelo", "Varianza vs liga (🟢🟡🔴⚪)", "Ancho del rango del equipo (relativo a su promedio, en esa condición: casa o fuera) dividido entre el ancho mediano de los equipos de la liga. 🟢 estable < 0.8×, 🟡 normal 0.8–1.2×, 🔴 volátil > 1.2×, ⚪ pocos datos = menos de 5 partidos efectivos en esa condición; ahí se usa la dispersión típica de la liga en lugar de la del equipo."),
    ("Modelo", "Encogimiento (K)", (f"Al calcular la fuerza de un equipo se le suman {mo.K_ENCOGE} partidos 'extra' al promedio de la liga, para que un equipo con pocos partidos o una racha rara no se vaya a extremos." if mo.K_ENCOGE else "Desactivado (K = 0): la fuerza de cada equipo es su promedio ponderado puro, sin acercarlo al promedio de la liga.") + " Se ajusta con K_ENCOGE en modelo.py."),
    ("Mercados", "Cuota justa", "(1 − probabilidad de devolución) dividido entre probabilidad de acierto. Si el acierto es imposible, no está disponible. Es la cuota a la que no ganas ni pierdes a largo plazo. Si la casa paga más que la justa, hay valor."),
    ("Mercados", "EV (valor esperado)", "probabilidad de acierto × cuota + probabilidad de devolución − 1. Positivo = a largo plazo ganas; negativo = pierdes. EV +0.10 = ganas 10 centavos por cada Q1 apostado, en promedio."),
    ("Mercados", "Over / Under", "Más de / menos de una línea. Total Over 2.5 goles = 3 o más goles en el partido. Las líneas .5 no permiten devolución; en líneas enteras la igualdad devuelve la apuesta y no cuenta como acierto."),
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
    ("Banca", "Kelly", "Maximiza el crecimiento logarítmico de la distribución de retornos, incluyendo devoluciones. Se usa el mínimo Kelly de los escenarios heurísticos calculados. Si falta distribución conjunta, hay duplicados o incompatibilidad, no se recomienda stake. Partidos distintos suponen independencia no validada."),
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
        return None if not math.isfinite(x) else float(x)
    return x


# ================================================================== CLI
if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit('Uso: python kuota.py <liga> "Local" "Visitante" [metrica]   ej. python kuota.py laliga "Real Madrid" "Barcelona" corners')
    liga, local, visitante = sys.argv[1:4]
    met = sys.argv[4] if len(sys.argv) > 4 else "goles"
    v = vista_partido(cargar(liga), liga, local, visitante, met)
    print(json.dumps(a_json(v), ensure_ascii=False, indent=1))

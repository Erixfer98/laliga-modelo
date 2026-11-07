"""
understat.py — xG (goles esperados) de cada partido desde Understat, solo para las 5 grandes ligas europeas.

Salida: datos/xg_<liga>.csv con fecha_dt, equipo_local_txt, equipo_visitante_txt, xg_local_val, xg_visitante_val
(nombres de equipo iguales a los de datos/bbdd_<liga>.csv). Es un archivo aparte: si Understat falla, la BBDD no se toca
y el Action sigue (se queda el último CSV de xG publicado).

Nombres: Understat escribe los equipos a su manera ("Real Oviedo", "Celta Vigo", ...). En vez de mantener un diccionario
a mano, cada nombre de Understat se empareja con el equipo de la BBDD con el que más veces coincide el calendario
(mismo partido el mismo día o con 1 día de diferencia). Después cada partido se une por temporada + local + visitante
(en una liga cada cruce local-visitante se juega una sola vez por temporada).

Uso:  python understat.py            -> las 5 ligas
      python understat.py laliga     -> una sola
"""

import codecs
import json
import re
import sys
from collections import Counter

import pandas as pd
import requests

# clave de la BBDD -> nombre de la liga en Understat
LIGAS = {"laliga": "La_liga", "premier": "EPL", "seriea": "Serie_A", "bundesliga": "Bundesliga", "ligue1": "Ligue_1"}
TEMPORADAS = {2025: "2025-26", 2026: "2026-27"}   # Understat nombra la temporada por el año en que empieza
CABECERAS = {"User-Agent": "Mozilla/5.0 (Kuota)", "X-Requested-With": "XMLHttpRequest"}
COLUMNAS = ["temporada_txt", "fecha_dt", "equipo_local_txt", "equipo_visitante_txt", "xg_local_val", "xg_visitante_val"]


def _partidos_crudos(liga_us: str, anio: int) -> list:
    """Lista de partidos de Understat (formato propio). Primero el JSON que usa la página; si no, el que venía incrustado en el HTML."""
    try:
        r = requests.get(f"https://understat.com/getLeagueData/{liga_us}/{anio}", headers=CABECERAS, timeout=30)
        r.raise_for_status()
        return r.json()["dates"]
    except Exception as e:
        primero = f"getLeagueData: {type(e).__name__} {str(e)[:120]}"
    r = requests.get(f"https://understat.com/league/{liga_us}/{anio}", headers=CABECERAS, timeout=30)
    m = re.search(r"datesData\s*=\s*JSON\.parse\('(.*?)'\)", r.text)
    if not m:
        raise RuntimeError(f"{primero} | página {r.status_code}, {len(r.text)} caracteres, sin datesData")
    return json.loads(codecs.decode(m.group(1), "unicode_escape"))


def descargar(liga_us: str) -> pd.DataFrame:
    """Partidos ya jugados de Understat: temporada, fecha, local, visitante (nombres de Understat), xG de cada uno."""
    filas = []
    for anio, temp in TEMPORADAS.items():
        for p in _partidos_crudos(liga_us, anio):
            if not p.get("isResult") or not p.get("xG") or p["xG"].get("h") is None:
                continue
            filas.append({"temporada_txt": temp, "fecha": pd.Timestamp(p["datetime"]).normalize(),
                          "us_local": p["h"]["title"], "us_visitante": p["a"]["title"],
                          "xg_local_val": round(float(p["xG"]["h"]), 2), "xg_visitante_val": round(float(p["xG"]["a"]), 2)})
    return pd.DataFrame(filas)


def emparejar_nombres(us: pd.DataFrame, bbdd: pd.DataFrame) -> dict:
    """Nombre de Understat -> nombre de la BBDD, por votos de calendario: cada partido de Understat vota por los equipos
    de la BBDD que jugaron en la misma posición (local/visitante) el mismo día (±1). El equipo real acumula ~1 voto por
    partido; los demás, pocos. Se asigna de mayor a menor voto sin repetir equipos."""
    votos = Counter()
    b = bbdd.assign(fecha=pd.to_datetime(bbdd.fecha_dt, dayfirst=True))
    por_dia = {f: g for f, g in b.groupby("fecha")}
    for p in us.itertuples():
        for d in (-1, 0, 1):
            g = por_dia.get(p.fecha + pd.Timedelta(days=d))
            if g is None:
                continue
            for x in g.itertuples():
                votos[(p.us_local, x.equipo_local_txt)] += 1
                votos[(p.us_visitante, x.equipo_visitante_txt)] += 1
    mapa, usados = {}, set()
    for (u, e), v in votos.most_common():
        if u not in mapa and e not in usados and v >= 3:
            mapa[u] = e
            usados.add(e)
    return mapa


def construir(liga: str, carpeta: str = "datos", us: pd.DataFrame = None) -> pd.DataFrame:
    """xG de cada partido de la BBDD de la liga (solo los que Understat tiene). `us` permite pasar datos ya bajados (pruebas)."""
    bbdd = pd.read_csv(f"{carpeta}/bbdd_{liga}.csv")
    us = descargar(LIGAS[liga]) if us is None else us
    mapa = emparejar_nombres(us, bbdd)
    us = us.assign(equipo_local_txt=us.us_local.map(mapa), equipo_visitante_txt=us.us_visitante.map(mapa))
    sin_nombre = sorted(set(us.us_local[us.equipo_local_txt.isna()]) | set(us.us_visitante[us.equipo_visitante_txt.isna()]))
    if sin_nombre:
        print(f"::warning::xG {liga}: equipos de Understat sin pareja en la BBDD: {sin_nombre}")
    llave = ["temporada_txt", "equipo_local_txt", "equipo_visitante_txt"]
    xg = bbdd[llave + ["fecha_dt"]].merge(us.dropna(subset=llave)[llave + ["xg_local_val", "xg_visitante_val"]], on=llave, how="inner")
    print(f"::notice::xG {liga}: {len(xg)} de {len(bbdd)} partidos de la BBDD ({len(xg) / max(len(bbdd), 1):.0%})")
    return xg[COLUMNAS]


def main(ligas: list) -> int:
    fallos = 0
    for liga in ligas:
        try:
            xg = construir(liga)
            if len(xg):
                xg.to_csv(f"datos/xg_{liga}.csv", index=False)
            else:
                print(f"AVISO {liga}: Understat no devolvió partidos; se deja el CSV anterior")
        except Exception as e:   # Understat caído o cambió: no frena el resto
            fallos += 1
            print(f"::warning::xG {liga}: no se pudo bajar de Understat ({e})")
    return fallos


if __name__ == "__main__":
    sys.exit(1 if main(sys.argv[1:] or list(LIGAS)) == len(sys.argv[1:] or LIGAS) else 0)

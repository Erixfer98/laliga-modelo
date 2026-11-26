"""
fotmob.py — xG (goles esperados) de cada partido desde FotMob: 5 grandes ligas europeas, Champions League y Europa League.
Reemplaza a understat.py (Understat en mantenimiento desde ~03/11/2026).

Salida:
  - datos/xg_<liga>.csv: temporada, fecha, local, visitante, xG de cada uno e id del partido en FotMob. Sirve de caché:
    cada corrida solo le pide a FotMob los partidos que todavía no tiene.
  - Las columnas xg_local_val y xg_visitante_val dentro de datos/bbdd_<liga>.csv y .xlsx (las agrega generar_bbdd.py
    a partir del CSV de arriba). Partido sin xG = celda vacía.
Si FotMob falla, no frena el Action: se queda el último xG publicado.

Nombres: FotMob escribe los equipos a su manera ("Atlético Madrid", "Inter", ...). Se emparejan primero los nombres
iguales sin acentos y después por rivales ya conocidos en el mismo partido (ver emparejar_nombres). Después cada partido
se une por local + visitante + fecha (±1 día: FotMob da la fecha en UTC).

Uso:  python fotmob.py             -> las 7 ligas (La Liga y Champions primero)
      python fotmob.py laliga      -> una sola
"""

import re
import sys
import time
import unicodedata
from collections import Counter

import pandas as pd
import requests

import generar_bbdd

# clave de la BBDD -> id de la liga en FotMob. El orden es la prioridad si se acaba el tiempo de la corrida.
LIGAS = {"laliga": 87, "champions": 42, "premier": 47, "seriea": 55, "bundesliga": 54, "ligue1": 53, "europa": 73}
N_TEMPORADAS = 2            # la actual y la anterior, igual que la BBDD
API = "https://www.fotmob.com/api/data"
CABECERAS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/131.0 Safari/537.36", "Accept-Language": "en-US,en;q=0.9"}
PAUSA = 0.25                # segundos entre partidos, para no saturar a FotMob
LIMITE_SEG = 20 * 60        # tiempo máximo por corrida; lo que falte se baja en la siguiente
COLUMNAS = ["temporada_txt", "fecha_dt", "equipo_local_txt", "equipo_visitante_txt",
            "xg_local_val", "xg_visitante_val", "fotmob_id_txt"]

_sesion = requests.Session()
_sesion.headers.update(CABECERAS)


def _json(ruta: str, **params):
    """GET a la API de FotMob con 3 intentos. Error si no hay respuesta válida."""
    error = ""
    for intento in range(3):
        try:
            r = _sesion.get(f"{API}/{ruta}", params=params, timeout=30)
            if r.status_code == 200 and r.json() is not None:
                return r.json()
            error = f"HTTP {r.status_code}"
        except (requests.RequestException, ValueError) as e:
            error = str(e)
        time.sleep(3 * (intento + 1))
    raise RuntimeError(f"FotMob {ruta} {params}: {error}")


def calendario(id_liga: int) -> pd.DataFrame:
    """Partidos terminados de las últimas N_TEMPORADAS en FotMob: id, fecha (UTC), local y visitante (nombres de FotMob)."""
    j = _json("leagues", id=id_liga)
    filas = []
    for temp in j["allAvailableSeasons"][:N_TEMPORADAS]:
        jt = j if temp == j["details"].get("selectedSeason") else _json("leagues", id=id_liga, season=temp)
        for m in jt["fixtures"]["allMatches"]:
            st = m.get("status", {})
            if st.get("finished") and not st.get("cancelled") and not st.get("awarded"):
                filas.append({"fotmob_id_txt": str(m["id"]),
                              "fecha": pd.Timestamp(st["utcTime"]).tz_convert(None).normalize(),
                              "fm_local": m["home"]["name"], "fm_visitante": m["away"]["name"]})
    return pd.DataFrame(filas, columns=["fotmob_id_txt", "fecha", "fm_local", "fm_visitante"]).drop_duplicates("fotmob_id_txt")


def leer_xg(detalle: dict, local: str = None):
    """(xG local, xG visitante) del detalle de un partido de FotMob; None si el partido no tiene xG.
    Si se pasa `local` (nombre de FotMob) y no coincide con el local del detalle, None: mejor vacío que al revés."""
    casa = (detalle.get("general") or {}).get("homeTeam", {}).get("name")
    if local and casa and _normal(casa) != _normal(local):   # sin acentos: «Ferencváros» = «Ferencvaros»
        return None
    try:
        grupos = detalle["content"]["stats"]["Periods"]["All"]["stats"]
    except (KeyError, TypeError):
        return None
    for g in grupos:
        for st in g.get("stats") or []:
            if st.get("key") == "expected_goals":
                vals = [x.get("value") for x in st.get("rawStats") or []]
                if len(vals) != 2 or any(v is None for v in vals):
                    return None
                return round(float(vals[0]), 2), round(float(vals[1]), 2)
    return None


def xg_partido(id_partido: str, local: str = None):
    return leer_xg(_json("matchDetails", matchId=id_partido), local)


def _normal(nombre: str) -> str:
    """Nombre sin acentos, mayúsculas ni signos: «Atlético Madrid» y «Atletico Madrid» quedan iguales."""
    s = unicodedata.normalize("NFKD", str(nombre)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def _asignar(votos: Counter, mapa: dict, minimo: int, solo_uno: bool = False) -> int:
    """Asigna a cada nombre de FotMob su equipo más votado si tiene al menos `minimo` votos, sin empate y sin repetir
    equipos de la BBDD. Devuelve cuántos asignó."""
    candidatos = {}
    for (f, e), v in votos.items():
        candidatos.setdefault(f, []).append((v, e))
    usados, n = set(mapa.values()), 0
    for f, lista in sorted(candidatos.items(), key=lambda kv: -max(kv[1])[0]):
        lista.sort(reverse=True)
        v, e = lista[0]
        if f in mapa or e in usados or v < minimo or (len(lista) > 1 and lista[1][0] == v):
            continue
        mapa[f], n = e, n + 1
        usados.add(e)
        if solo_uno:
            break
    return n


def emparejar_nombres(fm: pd.DataFrame, bbdd: pd.DataFrame) -> dict:
    """Nombre de FotMob -> nombre de la BBDD, en 3 pasos:
      1. Nombres iguales sin acentos ni mayúsculas («Atlético Madrid» = «Atletico Madrid»).
      2. Por rivales: si FotMob tiene «Inter» de visitante en casa del Real Madrid el 08/09 y la BBDD tiene
         Real Madrid - Internazionale ese día (±1), es un voto Inter -> Internazionale. Exacto aunque haya muchos
         partidos el mismo día (Champions).
      3. Si los rivales no alcanzan, votos de calendario (equipos que jugaron en la misma posición el mismo día; el
         mismo día pesa doble) para el nombre más claro, y se vuelve al paso 2."""
    equipos = sorted(set(bbdd.equipo_local_txt) | set(bbdd.equipo_visitante_txt))
    por_normal = {_normal(e): e for e in equipos}
    nombres_fm = set(fm.fm_local) | set(fm.fm_visitante)
    mapa = {f: por_normal[_normal(f)] for f in nombres_fm if _normal(f) in por_normal}
    b = bbdd.assign(fecha=pd.to_datetime(bbdd.fecha_dt, dayfirst=True))
    por_dia = {f: list(zip(g.equipo_local_txt, g.equipo_visitante_txt)) for f, g in b.groupby("fecha")}
    dias = lambda f: [(d, por_dia.get(f + pd.Timedelta(days=d), [])) for d in (-1, 0, 1)]
    while len(mapa) < len(nombres_fm):
        usados, votos = set(mapa.values()), Counter()
        for p in fm.itertuples():
            l, v = mapa.get(p.fm_local), mapa.get(p.fm_visitante)
            if (l is None) == (v is None):
                continue
            for _, partidos in dias(p.fecha):
                for bl, bv in partidos:
                    if l is not None and bl == l and bv not in usados:
                        votos[(p.fm_visitante, bv)] += 1
                    if v is not None and bv == v and bl not in usados:
                        votos[(p.fm_local, bl)] += 1
        if _asignar(votos, mapa, minimo=2):
            continue
        votos = Counter()
        for p in fm.itertuples():
            for d, partidos in dias(p.fecha):
                for bl, bv in partidos:
                    if p.fm_local not in mapa and bl not in usados:
                        votos[(p.fm_local, bl)] += 2 if d == 0 else 1
                    if p.fm_visitante not in mapa and bv not in usados:
                        votos[(p.fm_visitante, bv)] += 2 if d == 0 else 1
        if not _asignar(votos, mapa, minimo=4, solo_uno=True):
            break
    return mapa


def unir(fm: pd.DataFrame, bbdd: pd.DataFrame, mapa: dict) -> pd.DataFrame:
    """Cada partido de la BBDD con su id de FotMob: mismo local y visitante, fecha a 1 día o menos. Uno a uno."""
    llave = ["equipo_local_txt", "equipo_visitante_txt"]
    fm = fm.assign(equipo_local_txt=fm.fm_local.map(mapa), equipo_visitante_txt=fm.fm_visitante.map(mapa)).dropna(subset=llave)
    b = bbdd[["temporada_txt", "fecha_dt"] + llave].assign(fecha=pd.to_datetime(bbdd.fecha_dt, dayfirst=True))
    m = b.merge(fm[["fotmob_id_txt", "fecha", "fm_local"] + llave], on=llave, suffixes=("", "_fm"))
    m["dif"] = (m.fecha - m.fecha_fm).abs()
    m = m[m.dif <= pd.Timedelta(days=1)].sort_values(["dif", "fecha"])
    return m.drop_duplicates(["fecha_dt", "equipo_local_txt"]).drop_duplicates("fotmob_id_txt")


def construir(liga: str, carpeta: str = "datos", fm: pd.DataFrame = None, obtener=xg_partido, hasta: float = None) -> pd.DataFrame:
    """xG de cada partido de la BBDD de la liga que FotMob tenga. Usa datos/xg_<liga>.csv como caché y solo pide los
    partidos nuevos hasta la hora `hasta` (time.time()). `fm` y `obtener` permiten pruebas sin internet."""
    bbdd = pd.read_csv(f"{carpeta}/bbdd_{liga}.csv")
    fm = calendario(LIGAS[liga]) if fm is None else fm
    mapa = emparejar_nombres(fm, bbdd)
    sin_pareja = sorted((set(bbdd.equipo_local_txt) | set(bbdd.equipo_visitante_txt)) - set(mapa.values()))
    if sin_pareja:
        print(f"::warning::xG {liga}: equipos de la BBDD sin pareja en FotMob: {sin_pareja}")
    unidos = unir(fm, bbdd, mapa)

    cache = {}
    ruta = f"{carpeta}/xg_{liga}.csv"
    try:
        previo = pd.read_csv(ruta, dtype={"fotmob_id_txt": str})
        cache = {r.fotmob_id_txt: (r.xg_local_val, r.xg_visitante_val) for r in previo.dropna(subset=["fotmob_id_txt"]).itertuples()}
    except (FileNotFoundError, ValueError, KeyError):
        pass

    filas, nuevos, pendientes = [], 0, 0
    for p in unidos.itertuples():
        xg = cache.get(p.fotmob_id_txt)
        if xg is None:
            if hasta is not None and time.time() > hasta:
                pendientes += 1
                continue
            try:
                xg = obtener(p.fotmob_id_txt, p.fm_local)
            except Exception as e:
                print(f"AVISO xG {liga}: partido {p.fotmob_id_txt} sin respuesta ({e})")
                xg = None
            nuevos += xg is not None
            if obtener is xg_partido:
                time.sleep(PAUSA)
        if xg is not None:
            filas.append([p.temporada_txt, p.fecha_dt, p.equipo_local_txt, p.equipo_visitante_txt, xg[0], xg[1], p.fotmob_id_txt])
    xg = pd.DataFrame(filas, columns=COLUMNAS)
    xg = xg.assign(_f=pd.to_datetime(xg.fecha_dt, dayfirst=True)).sort_values(["_f", "equipo_local_txt"]).drop(columns="_f")
    aviso = f"; faltan {pendientes} por bajar (siguiente corrida)" if pendientes else ""
    print(f"::notice::xG {liga}: {len(xg)} de {len(bbdd)} partidos de la BBDD ({len(xg) / max(len(bbdd), 1):.0%}), "
          f"{nuevos} nuevos de FotMob{aviso}")
    return xg.reset_index(drop=True)


def main(ligas: list) -> int:
    hasta, fallos = time.time() + LIMITE_SEG, 0
    for liga in ligas:
        try:
            xg = construir(liga, hasta=hasta)
            if len(xg):
                xg.to_csv(f"datos/xg_{liga}.csv", index=False)
                generar_bbdd.refrescar(liga)     # escribe las columnas de xG en bbdd_<liga>.csv y .xlsx
            else:
                print(f"AVISO {liga}: FotMob no devolvió xG; se deja lo anterior")
        except Exception as e:   # FotMob caído o cambió: no frena el resto
            fallos += 1
            print(f"::warning::xG {liga}: no se pudo bajar de FotMob ({e})")
    return fallos


if __name__ == "__main__":
    ligas = sys.argv[1:] or list(LIGAS)
    sys.exit(1 if main(ligas) == len(ligas) else 0)

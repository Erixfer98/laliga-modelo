"""
espn.py — fuente ESPN para ligas que football-data.co.uk no cubre con estadisticas (hoy: Liga MX).
Portado del notebook cargar_estadisticas_espn_v2 (Colab) que ya genero la BBDD de Liga MX.

Como funciona:
  1. scoreboard por dia (mex.1): lista de partidos terminados con goles finales y, por equipo,
     tiros, tiros a puerta, corners, faltas, amarillas y rojas.
  2. summary por partido: goles al descanso (keyEvents con respaldo en linescores) y tarjetas
     (keyEvents con respaldo en boxscore).
  3. Temporada por fecha: enero-junio = "Clausura AAAA", julio-diciembre = "Apertura AAAA".
     Hora local = UTC - 6 (Mexico no cambia de horario desde 2022).
  4. Incremental: si ya existe datos/bbdd_ligamx.csv, solo consulta desde el ultimo partido menos
     DIAS_REPASO dias y mezcla (los partidos viejos no se vuelven a pedir). --completo lo rehace todo.

Devuelve un DataFrame con las mismas columnas de entrada que transformar() en generar_bbdd.py.
"""

import datetime as dt
import time

import pandas as pd
import requests

SB = "https://site.api.espn.com/apis/site/v2/sports/soccer/{liga}/scoreboard"
SUM = "https://site.api.espn.com/apis/site/v2/sports/soccer/{liga}/summary"
PAUSA = 0.3            # segundos entre llamadas, como en el notebook
DIAS_REPASO = 4        # en modo incremental se vuelve a pedir desde el ultimo partido menos estos dias

# nombre normalizado en la BBDD -> como lo escribe ESPN (displayName, shortDisplayName, name, location, abbreviation)
ALIAS_LIGAMX = {
    "America": ["club america", "america"], "Atlante": ["atlante"], "Atlas": ["atlas"],
    "Atletico San Luis": ["atletico de san luis", "atletico san luis", "san luis", "atl. san luis"],
    "Cruz Azul": ["cruz azul"], "Guadalajara": ["guadalajara", "chivas", "cd guadalajara"], "FC Juarez": ["fc juarez", "juarez", "bravos"],
    "Leon": ["leon", "club leon"], "Mazatlan": ["mazatlan fc", "mazatlan"], "Monterrey": ["monterrey", "rayados"],
    "Necaxa": ["necaxa"], "Pachuca": ["pachuca"], "Puebla": ["puebla"], "Pumas UNAM": ["pumas unam", "unam", "pumas"],
    "Queretaro": ["queretaro"], "Santos Laguna": ["santos laguna", "santos"], "Tigres UANL": ["tigres uanl", "tigres", "uanl"],
    "Tijuana": ["club tijuana", "tijuana", "xolos"], "Toluca": ["toluca", "deportivo toluca"],
}
STATS = {"totalShots": "tiros", "shotsOnTarget": "tiros_a_puerta", "wonCorners": "corners",
         "foulsCommitted": "faltas", "yellowCards": "amarillas", "redCards": "rojas"}


def norm(s: str) -> str:
    return (s or "").lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").replace("ñ", "n")


def nombre_equipo(team: dict, alias: dict) -> str:
    """Nombre normalizado de la BBDD; si no esta en el diccionario se deja el displayName de ESPN."""
    nombres = {norm(team.get(k, "")) for k in ("displayName", "shortDisplayName", "name", "location", "abbreviation")}
    for bbdd, variantes in alias.items():
        if any(norm(a) in nombres for a in variantes):
            return bbdd
    print("AVISO: equipo sin nombre normalizado, se deja como viene:", team.get("displayName"))
    return team.get("displayName", "")


def get(url: str, **params) -> dict:
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    time.sleep(PAUSA)
    return r.json()


def stat(comp: dict, name: str):
    for s in comp.get("statistics", []):
        if s.get("name") == name:
            try:
                return int(float(s.get("displayValue", s.get("value"))))
            except Exception:
                return None
    return None


def descanso_y_tarjetas(liga: str, event_id: str, hid: str, aid: str) -> dict:
    """Goles al descanso y tarjetas por equipo desde el summary del partido (misma logica del notebook)."""
    s = get(SUM.format(liga=liga), event=event_id)
    ht, yc, rc = {hid: 0, aid: 0}, {hid: 0, aid: 0}, {hid: 0, aid: 0}
    for k in s.get("keyEvents", []):
        typ = norm(k.get("type", {}).get("text", "")); tid = k.get("team", {}).get("id"); per = k.get("period", {}).get("number")
        if tid not in ht:
            continue
        if k.get("scoringPlay") and per == 1:
            ht[tid] += 1
        elif "yellow" in typ:
            yc[tid] += 1
        elif "red" in typ:
            rc[tid] += 1
    for c in s.get("header", {}).get("competitions", [{}])[0].get("competitors", []):   # respaldo descanso
        ls = c.get("linescores", [])
        if ls and c.get("team", {}).get("id") in ht and "value" in ls[0]:
            ht[c["team"]["id"]] = int(ls[0]["value"])
    for t in s.get("boxscore", {}).get("teams", []):                                    # respaldo tarjetas
        tid = t.get("team", {}).get("id")
        for st in t.get("statistics", []):
            n = st.get("name", "")
            if tid in yc and n == "yellowCards" and yc[tid] == 0:
                yc[tid] = int(float(st.get("displayValue", 0)))
            if tid in rc and n == "redCards" and rc[tid] == 0:
                rc[tid] = int(float(st.get("displayValue", 0)))
    return {"ht_l": ht[hid], "ht_v": ht[aid], "yc_l": yc[hid], "yc_v": yc[aid], "rc_l": rc[hid], "rc_v": rc[aid]}


def temporada(fecha: dt.date) -> str:
    return f"{'Clausura' if fecha.month <= 6 else 'Apertura'} {fecha.year}"


def partidos_dia(liga: str, dia: dt.date, alias: dict, utc_offset: int) -> list:
    filas = []
    for e in get(SB.format(liga=liga), dates=dia.strftime("%Y%m%d"), limit=100).get("events", []):
        if not e.get("status", {}).get("type", {}).get("completed"):
            continue
        comp = e["competitions"][0]; ts = comp["competitors"]
        home = next((t for t in ts if t["homeAway"] == "home"), None); away = next((t for t in ts if t["homeAway"] == "away"), None)
        if not home or not away:
            continue
        kick = dt.datetime.strptime(e["date"], "%Y-%m-%dT%H:%MZ")
        local = kick + dt.timedelta(hours=utc_offset)
        f = {"Date": local.strftime("%d/%m/%Y"), "Time": local.strftime("%H:%M"), "hora_utc": kick.strftime("%H:%M"),
             "temporada_txt": temporada(local.date()),
             "HomeTeam": nombre_equipo(home["team"], alias), "AwayTeam": nombre_equipo(away["team"], alias),
             "FTHG": int(float(home.get("score", 0))), "FTAG": int(float(away.get("score", 0)))}
        for key, col in STATS.items():
            f[f"{col}_l"], f[f"{col}_v"] = stat(home, key), stat(away, key)
        try:
            f.update(descanso_y_tarjetas(liga, e["id"], home["team"]["id"], away["team"]["id"]))
        except Exception as ex:
            print(f"AVISO: sin summary para {f['Date']} {f['HomeTeam']}-{f['AwayTeam']}: {ex}")
            f.update({"ht_l": None, "ht_v": None, "yc_l": None, "yc_v": None, "rc_l": None, "rc_v": None})
        # tarjetas: el summary (keyEvents) es la fuente principal, como en el notebook; scoreboard es respaldo
        for a, b in (("amarillas", "yc"), ("rojas", "rc")):
            for lado in ("l", "v"):
                if f.get(f"{b}_{lado}") is not None:
                    f[f"{a}_{lado}"] = f[f"{b}_{lado}"]
        if f["ht_l"] is not None and (f["ht_l"] > f["FTHG"] or f["ht_v"] > f["FTAG"]):
            print(f"REVISAR descanso {f['Date']} {f['HomeTeam']}-{f['AwayTeam']}: HT {f['ht_l']}-{f['ht_v']} vs FT {f['FTHG']}-{f['FTAG']}")
        filas.append(f)
    return filas


def a_crudo(filas: list) -> pd.DataFrame:
    """Al formato de entrada de transformar(): mismas columnas que football-data + temporada_txt."""
    d = pd.DataFrame(filas)
    if d.empty:
        return d
    return pd.DataFrame({
        "temporada_txt": d["temporada_txt"], "Date": d["Date"], "Time": d["Time"], "hora_utc": d["hora_utc"],
        "HomeTeam": d["HomeTeam"], "AwayTeam": d["AwayTeam"], "FTHG": d["FTHG"], "FTAG": d["FTAG"],
        "HTHG": d["ht_l"], "HTAG": d["ht_v"], "HS": d["tiros_l"], "AS": d["tiros_v"], "HST": d["tiros_a_puerta_l"], "AST": d["tiros_a_puerta_v"],
        "HC": d["corners_l"], "AC": d["corners_v"], "HF": d["faltas_l"], "AF": d["faltas_v"],
        "HY": d["amarillas_l"], "AY": d["amarillas_v"], "HR": d["rojas_l"], "AR": d["rojas_v"],
    })


def csv_a_crudo(ruta: str) -> pd.DataFrame:
    """Lee un bbdd_<liga>.csv ya generado y lo devuelve en formato crudo para mezclarlo con lo nuevo."""
    d = pd.read_csv(ruta)
    return pd.DataFrame({
        "temporada_txt": d["temporada_txt"], "Date": d["fecha_dt"], "Time": d["hora_local_txt"], "hora_utc": d["hora_utc_txt"],
        "HomeTeam": d["equipo_local_txt"], "AwayTeam": d["equipo_visitante_txt"], "FTHG": d["goles_local_val"], "FTAG": d["goles_visitante_val"],
        "HTHG": d["goles_local_primer_tiempo_val"], "HTAG": d["goles_visitante_primer_tiempo_val"],
        "HS": d["tiros_local_val"], "AS": d["tiros_visitante_val"], "HST": d["tiros_a_puerta_local_val"], "AST": d["tiros_a_puerta_visitante_val"],
        "HC": d["corners_local_val"], "AC": d["corners_visitante_val"], "HF": d["faltas_local_val"], "AF": d["faltas_visitante_val"],
        "HY": d["amarillas_local_val"], "AY": d["amarillas_visitante_val"], "HR": d["rojas_local_val"], "AR": d["rojas_visitante_val"],
    })


def descargar(liga: str, desde: dt.date, hasta: dt.date, alias: dict, utc_offset: int = -6, existente: str = None) -> pd.DataFrame:
    """Partidos terminados entre desde y hasta (inclusive). Si existente (csv) se pasa, solo se consulta
    desde el ultimo partido menos DIAS_REPASO dias y se mezcla con lo ya guardado."""
    previo = pd.DataFrame()
    if existente:
        try:
            previo = csv_a_crudo(existente)
            ultimo = pd.to_datetime(previo["Date"], dayfirst=True).max().date()
            desde = max(desde, ultimo - dt.timedelta(days=DIAS_REPASO))
        except Exception as ex:
            print(f"AVISO: no se pudo leer {existente} ({ex}); se descarga completo")
            previo = pd.DataFrame()
    print(f"   ESPN {liga}: consultando del {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}")
    filas, dia = [], desde
    while dia <= hasta:
        try:
            filas += partidos_dia(liga, dia, alias, utc_offset)
        except Exception as ex:
            print(f"AVISO: fallo el dia {dia}: {ex}")
        dia += dt.timedelta(days=1)
    nuevo = a_crudo(filas)
    print(f"   ESPN {liga}: {len(nuevo)} partidos nuevos o repasados, {len(previo)} previos")
    todo = pd.concat([nuevo, previo], ignore_index=True) if not previo.empty else nuevo
    # lo nuevo va primero: si un partido se repasa, gana la version recien descargada
    todo = todo.drop_duplicates(subset=["Date", "HomeTeam"], keep="first")
    todo["_f"] = pd.to_datetime(todo["Date"], dayfirst=True)
    return todo.sort_values("_f").drop(columns="_f").reset_index(drop=True)

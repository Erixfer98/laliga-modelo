"""
generar_bbdd.py — descarga football-data.co.uk y regenera datos/bbdd_<liga>.xlsx + .csv para las 5 grandes ligas
(28 columnas, hojas partidos + diccionario). Cada corrida borra y reescribe todo.
Uso: python generar_bbdd.py            (todas las ligas)
     python generar_bbdd.py premier    (solo una)
"""
from datetime import datetime
from io import StringIO
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


TEMPORADAS = {          # codigo football-data -> nombre en la BBDD
    "2526": "2025-26",
    "2627": "2026-27",
}
URL = "https://www.football-data.co.uk/mmz4281/{codigo}/{div}.csv"
SALIDA = "datos/bbdd_laliga.xlsx"   # mismo nombre siempre; se sobrescribe completo en cada corrida

# nombre football-data -> nombre largo normalizado, sin acentos
EQUIPOS_LALIGA = {
    "Alaves": "Alaves", "Almeria": "Almeria", "Ath Bilbao": "Athletic Club",
    "Ath Madrid": "Atletico Madrid", "Barcelona": "Barcelona", "Betis": "Real Betis",
    "Cadiz": "Cadiz", "Celta": "Celta de Vigo", "Elche": "Elche", "Espanol": "Espanyol",
    "Getafe": "Getafe", "Girona": "Girona", "Granada": "Granada", "Las Palmas": "Las Palmas",
    "Leganes": "Leganes", "Levante": "Levante", "Mallorca": "Mallorca", "Osasuna": "Osasuna",
    "Oviedo": "Real Oviedo", "Real Madrid": "Real Madrid", "Sevilla": "Sevilla",
    "Sociedad": "Real Sociedad", "Valencia": "Valencia", "Valladolid": "Real Valladolid",
    "Vallecano": "Rayo Vallecano", "Villarreal": "Villarreal",
    "La Coruna": "Deportivo La Coruna", "Malaga": "Malaga", "Santander": "Racing Santander",
}

EQUIPOS_PREMIER = {"Man United": "Manchester United", "Man City": "Manchester City", "Nott'm Forest": "Nottingham Forest",
                   "Wolves": "Wolverhampton", "Tottenham": "Tottenham", "Newcastle": "Newcastle", "West Ham": "West Ham",
                   "Brighton": "Brighton", "Crystal Palace": "Crystal Palace", "Aston Villa": "Aston Villa", "Bournemouth": "Bournemouth",
                   "Brentford": "Brentford", "Fulham": "Fulham", "Everton": "Everton", "Liverpool": "Liverpool", "Arsenal": "Arsenal",
                   "Chelsea": "Chelsea", "Leeds": "Leeds United", "Burnley": "Burnley", "Sunderland": "Sunderland", "Ipswich": "Ipswich",
                   "Leicester": "Leicester", "Southampton": "Southampton"}
EQUIPOS_SERIEA = {"Inter": "Inter", "Milan": "AC Milan", "Roma": "AS Roma", "Verona": "Hellas Verona", "Juventus": "Juventus",
                  "Napoli": "Napoli", "Atalanta": "Atalanta", "Lazio": "Lazio", "Fiorentina": "Fiorentina", "Bologna": "Bologna",
                  "Torino": "Torino", "Udinese": "Udinese", "Genoa": "Genoa", "Cagliari": "Cagliari", "Como": "Como", "Lecce": "Lecce",
                  "Parma": "Parma", "Sassuolo": "Sassuolo", "Pisa": "Pisa", "Cremonese": "Cremonese", "Empoli": "Empoli", "Venezia": "Venezia",
                  "Monza": "Monza"}
EQUIPOS_BUNDESLIGA = {"Bayern Munich": "Bayern Munich", "Dortmund": "Borussia Dortmund", "Leverkusen": "Bayer Leverkusen",
                      "RB Leipzig": "RB Leipzig", "Ein Frankfurt": "Eintracht Frankfurt", "M'gladbach": "Borussia Monchengladbach",
                      "Stuttgart": "Stuttgart", "Wolfsburg": "Wolfsburg", "Freiburg": "Freiburg", "Hoffenheim": "Hoffenheim", "Mainz": "Mainz",
                      "Augsburg": "Augsburg", "Werder Bremen": "Werder Bremen", "Union Berlin": "Union Berlin", "St Pauli": "St. Pauli",
                      "Heidenheim": "Heidenheim", "FC Koln": "FC Koln", "Hamburg": "Hamburger SV", "Bochum": "Bochum", "Holstein Kiel": "Holstein Kiel"}
EQUIPOS_LIGUE1 = {"Paris SG": "Paris Saint-Germain", "Marseille": "Marseille", "Lyon": "Lyon", "Monaco": "Monaco", "Lille": "Lille",
                  "Nice": "Nice", "Lens": "Lens", "Rennes": "Rennes", "Strasbourg": "Strasbourg", "Brest": "Brest", "Toulouse": "Toulouse",
                  "Nantes": "Nantes", "Auxerre": "Auxerre", "Angers": "Angers", "Le Havre": "Le Havre", "Lorient": "Lorient", "Metz": "Metz",
                  "Paris FC": "Paris FC", "Reims": "Reims", "St Etienne": "Saint-Etienne", "Montpellier": "Montpellier"}

# clave -> division football-data, nombre, diccionario de equipos. Salida: datos/bbdd_<clave>.xlsx y .csv
LIGAS = {
    "laliga":     {"div": "SP1", "nombre": "La Liga",    "pais": "Espana",     "tz": "Europe/Madrid", "equipos": EQUIPOS_LALIGA},
    "premier":    {"div": "E0",  "nombre": "Premier League", "pais": "Inglaterra", "tz": "Europe/London", "equipos": EQUIPOS_PREMIER},
    "seriea":     {"div": "I1",  "nombre": "Serie A",    "pais": "Italia",     "tz": "Europe/Rome",   "equipos": EQUIPOS_SERIEA},
    "bundesliga": {"div": "D1",  "nombre": "Bundesliga", "pais": "Alemania",   "tz": "Europe/Berlin", "equipos": EQUIPOS_BUNDESLIGA},
    "ligue1":     {"div": "F1",  "nombre": "Ligue 1",    "pais": "Francia",    "tz": "Europe/Paris",  "equipos": EQUIPOS_LIGUE1},
}
EQUIPOS = EQUIPOS_LALIGA   # se reasigna por liga en el ciclo principal
TZ_LOCAL = "Europe/Madrid"

COLUMNAS = [
    "temporada_txt", "jornada_val", "fecha_dt", "hora_local_txt", "hora_utc_txt",
    "equipo_local_txt", "equipo_visitante_txt", "goles_local_val", "goles_visitante_val",
    "goles_local_primer_tiempo_val", "goles_local_segundo_tiempo_val",
    "goles_visitante_primer_tiempo_val", "goles_visitante_segundo_tiempo_val",
    "goles_total_primer_tiempo_val", "goles_total_segundo_tiempo_val",
    "goles_total_partido_val", "tiros_local_val", "tiros_visitante_val",
    "tiros_a_puerta_local_val", "tiros_a_puerta_visitante_val", "corners_local_val",
    "corners_visitante_val", "faltas_local_val", "faltas_visitante_val",
    "amarillas_local_val", "amarillas_visitante_val", "rojas_local_val", "rojas_visitante_val",
]
ANCHOS = [11, 13, 13, 13.5, 14.2, 13, 15.3, 16.7, 19.7, 24.2, 18.7, 13, 13, 13, 13,
          17.3, 12.3, 14.8, 17.8, 20, 13.5, 16, 13, 15.3, 14.8, 17.3, 12.3, 14.8]


def descargar(codigo: str, div: str = "SP1") -> pd.DataFrame:
    r = requests.get(URL.format(codigo=codigo, div=div), timeout=30)
    r.raise_for_status()
    df = pd.read_csv(StringIO(r.text))
    df = df.dropna(subset=["HomeTeam", "AwayTeam", "FTHG", "FTAG"])
    df["temporada_txt"] = TEMPORADAS[codigo]
    return df


def a_horas(fecha: str, hora_uk: str):
    """football-data publica la hora en horario de Reino Unido. Devuelve (hora Espana, hora UTC)."""
    if pd.isna(hora_uk) or not str(hora_uk).strip():
        return "", ""
    uk = datetime.strptime(f"{fecha} {hora_uk}", "%d/%m/%Y %H:%M").replace(tzinfo=ZoneInfo("Europe/London"))
    es = uk.astimezone(ZoneInfo(TZ_LOCAL)).strftime("%H:%M")
    utc = uk.astimezone(ZoneInfo("UTC")).strftime("%H:%M")
    return es, utc


def jornada_estimada(df: pd.DataFrame) -> pd.Series:
    """football-data no trae jornada. Se estima: partido n-esimo de cada equipo en la temporada.
    Se toma el mayor entre local y visitante para que ambos coincidan.
    Un partido aplazado se cuenta cuando se jugo, no en su jornada oficial."""
    df = df.sort_values(["temporada_txt", "_fecha"]).copy()
    n_local, n_visita = [], []
    for temp, g in df.groupby("temporada_txt", sort=False):
        conteo = {}
        for _, f in g.iterrows():
            conteo[f["HomeTeam"]] = conteo.get(f["HomeTeam"], 0) + 1
            conteo[f["AwayTeam"]] = conteo.get(f["AwayTeam"], 0) + 1
            n_local.append(conteo[f["HomeTeam"]])
            n_visita.append(conteo[f["AwayTeam"]])
    df["jornada_val"] = [max(a, b) for a, b in zip(n_local, n_visita)]
    return df


def transformar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["_fecha"] = pd.to_datetime(df["Date"], dayfirst=True)
    df = jornada_estimada(df)
    horas = [a_horas(d, t) for d, t in zip(df["Date"], df.get("Time", pd.Series([""] * len(df))))]
    df["hora_local_txt"] = [h[0] for h in horas]
    df["hora_utc_txt"] = [h[1] for h in horas]
    faltantes = set(df["HomeTeam"]) | set(df["AwayTeam"])
    faltantes -= EQUIPOS.keys()
    if faltantes:
        print("AVISO: equipos sin nombre normalizado, se dejan como vienen:", faltantes)

    out = pd.DataFrame({
        "temporada_txt": df["temporada_txt"],
        "jornada_val": df["jornada_val"],
        "fecha_dt": df["_fecha"].dt.strftime("%d/%m/%Y"),
        "hora_local_txt": df["hora_local_txt"],
        "hora_utc_txt": df["hora_utc_txt"],
        "equipo_local_txt": df["HomeTeam"].map(lambda x: EQUIPOS.get(x, x)),
        "equipo_visitante_txt": df["AwayTeam"].map(lambda x: EQUIPOS.get(x, x)),
        "goles_local_val": df["FTHG"], "goles_visitante_val": df["FTAG"],
        "goles_local_primer_tiempo_val": df["HTHG"], "goles_visitante_primer_tiempo_val": df["HTAG"],
        "tiros_local_val": df["HS"], "tiros_visitante_val": df["AS"],
        "tiros_a_puerta_local_val": df["HST"], "tiros_a_puerta_visitante_val": df["AST"],
        "corners_local_val": df["HC"], "corners_visitante_val": df["AC"],
        "faltas_local_val": df["HF"], "faltas_visitante_val": df["AF"],
        "amarillas_local_val": df["HY"], "amarillas_visitante_val": df["AY"],
        "rojas_local_val": df["HR"], "rojas_visitante_val": df["AR"],
    })
    # deduplicar: la fuente republica el CSV completo cada vez
    out = out.drop_duplicates(subset=["fecha_dt", "equipo_local_txt"]).reset_index(drop=True)
    return out


FUENTE = Font(name="Arial", size=10)
FUENTE_HDR = Font(name="Arial", size=10, bold=True, color="FFFFFF")
RELLENO_HDR = PatternFill("solid", fgColor="000000")
FINO = Side(style="thin")
BORDE = Border(left=FINO, right=FINO, top=FINO, bottom=FINO)


def escribir_hoja(ws, encabezados, filas, anchos, alto_hdr, wrap_cuerpo=False):
    ws.append(encabezados)
    for c in ws[1]:
        c.font, c.fill, c.border = FUENTE_HDR, RELLENO_HDR, BORDE
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = alto_hdr
    for fila in filas:
        ws.append(fila)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font, c.border = FUENTE, BORDE
            c.alignment = Alignment(horizontal="left", vertical="top", wrap_text=wrap_cuerpo)
    for i, a in enumerate(anchos, start=1):
        ws.column_dimensions[get_column_letter(i)].width = a


def valor(x):
    return None if pd.isna(x) else (int(x) if isinstance(x, float) and x.is_integer() else x)


def fila_partido(i, p):  # i = numero de fila en Excel
    return [
        p["temporada_txt"], int(p["jornada_val"]), p["fecha_dt"], p["hora_local_txt"], p["hora_utc_txt"],
        p["equipo_local_txt"], p["equipo_visitante_txt"],
        valor(p["goles_local_val"]), valor(p["goles_visitante_val"]),
        valor(p["goles_local_primer_tiempo_val"]),
        valor(p["goles_local_val"] - p["goles_local_primer_tiempo_val"]),
        valor(p["goles_visitante_primer_tiempo_val"]),
        valor(p["goles_visitante_val"] - p["goles_visitante_primer_tiempo_val"]),
        valor(p["goles_local_primer_tiempo_val"] + p["goles_visitante_primer_tiempo_val"]),
        valor(p["goles_local_val"] + p["goles_visitante_val"] - p["goles_local_primer_tiempo_val"] - p["goles_visitante_primer_tiempo_val"]),
        valor(p["goles_local_val"] + p["goles_visitante_val"]),
        valor(p["tiros_local_val"]), valor(p["tiros_visitante_val"]),
        valor(p["tiros_a_puerta_local_val"]), valor(p["tiros_a_puerta_visitante_val"]),
        valor(p["corners_local_val"]), valor(p["corners_visitante_val"]),
        valor(p["faltas_local_val"]), valor(p["faltas_visitante_val"]),
        valor(p["amarillas_local_val"]), valor(p["amarillas_visitante_val"]),
        valor(p["rojas_local_val"]), valor(p["rojas_visitante_val"]),
    ]


def diccionario(partidos: pd.DataFrame, fecha_carga: str):
    cobertura = ", ".join(f"{t}: {n} partidos" for t, n in partidos["temporada_txt"].value_counts(sort=False).items())
    equipos = ", ".join(sorted(set(partidos["equipo_local_txt"]) | set(partidos["equipo_visitante_txt"])))
    return [
        ["CONVENCION DE SUFIJOS", None,
         "_dt = fecha. _txt = texto. _val = numero. _flag = si/no (0-1). Todo en minusculas y snake_case, sin acentos, sin espacios, sin caracteres especiales.",
         "Misma convencion que la BBDD de Liga MX. Hoy no hay ninguna columna _flag."],
        ["temporada_txt", "texto", 'Temporada en formato "2025-26" (ago-may).', "Codigo football-data.co.uk (2526, 2627)."],
        ["jornada_val", "numero", "Jornada ESTIMADA (1-38): partido n-esimo de cada equipo en la temporada, ordenado por fecha.",
         "football-data.co.uk no publica la jornada oficial. Un partido aplazado se cuenta en la jornada en que se jugo, no en la oficial."],
        ["fecha_dt", "fecha", "Fecha del partido, dd/mm/aaaa, en hora local de Espana.", "Columna Date de football-data.co.uk."],
        ["hora_local_txt", "texto", "Hora de inicio en hora local del pais de la liga, formato HH:MM. Vacia = no publicada.",
         "Columna Time de football-data.co.uk viene en hora de Reino Unido; se convierte a la hora local de la liga (zona horaria del pais)."],
        ["hora_utc_txt", "texto", "Hora de inicio en UTC, formato HH:MM.", "Conversion desde la hora de Reino Unido con zona horaria Europe/London. Insumo directo para Open-Meteo."],
        ["equipo_local_txt / equipo_visitante_txt", "texto", f"Equipos con nombre largo normalizado, sin acentos: {equipos}.",
         "Diccionario EQUIPOS del script (ej. Ath Madrid -> Atletico Madrid, Sociedad -> Real Sociedad)."],
        ["goles_local_val / goles_visitante_val", "numero", "Goles al final del partido.", "FTHG / FTAG de football-data.co.uk."],
        ["goles_*_primer_tiempo_val", "numero", "Goles al descanso.", "HTHG / HTAG de football-data.co.uk."],
        ["goles_*_segundo_tiempo_val", "numero", "Formula: goles finales menos goles al descanso.", "Calculado en el script."],
        ["goles_total_primer_tiempo_val / goles_total_segundo_tiempo_val", "numero", "Formula: suma de ambos equipos por tiempo.", "Calculado en el script."],
        ["goles_total_partido_val", "numero", "Formula: goles local + goles visitante.", "Calculado en el script."],
        ["tiros_*, tiros_a_puerta_*, corners_*, faltas_*, amarillas_*, rojas_*", "numero", "Estadisticas del partido por equipo.",
         "HS/AS, HST/AST, HC/AC, HF/AF, HY/AY, HR/AR de football-data.co.uk."],
        [None, None, None, None],
        ["HANDICAP / CUOTAS", None, "Sin columnas de handicap ni de cuotas, igual que la BBDD de Liga MX.", "A peticion."],
        ["COBERTURA", None, f"{len(partidos)} partidos ({cobertura}). 28 columnas. Cargado el {fecha_carga}.", "Descarga automatica con generar_bbdd.py."],
        ["LLAVE SUGERIDA", None, "No hay id unico. Para SQL sirve fecha_dt + equipo_local_txt, que no se repite en toda la tabla.",
         "El script deduplica por esa llave en cada corrida porque la fuente republica el CSV completo."],
        ["COMO ACTUALIZAR", None, "Volver a correr generar_bbdd.py: descarga los CSV de las temporadas configuradas y regenera el Excel completo de cada liga.",
         "football-data.co.uk actualiza normalmente martes y viernes."],
    ]


def generar(partidos: pd.DataFrame, salida: str = SALIDA):
    wb = Workbook()
    ws = wb.active
    ws.title = "partidos"
    filas = [fila_partido(i, p) for i, (_, p) in enumerate(partidos.iterrows(), start=2)]
    escribir_hoja(ws, COLUMNAS, filas, ANCHOS, alto_hdr=79.75)
    ws.freeze_panes = "H2"
    ws.auto_filter.ref = f"A1:AB{ws.max_row}"

    wd = wb.create_sheet("diccionario")
    escribir_hoja(wd, ["columna", "tipo", "definicion", "fuente / supuesto"],
                  diccionario(partidos, datetime.now().strftime("%d/%m/%Y")),
                  [38, 10, 62, 58], alto_hdr=20, wrap_cuerpo=True)
    wb.save(salida)
    # copia CSV con los mismos valores: es lo que leen modelo.py y la app
    pd.DataFrame([f for f in filas], columns=COLUMNAS).to_csv(salida.replace(".xlsx", ".csv"), index=False)
    print(f"OK -> {salida} y .csv ({len(partidos)} partidos)")

if __name__ == "__main__":
    import os
    import sys
    os.makedirs("datos", exist_ok=True)
    claves = sys.argv[1:] or list(LIGAS)
    for clave in claves:
        liga = LIGAS[clave]
        EQUIPOS, TZ_LOCAL = liga["equipos"], liga["tz"]
        print(f"== {liga['nombre']} ({liga['div']})")
        try:
            crudo = pd.concat([descargar(c, liga["div"]) for c in TEMPORADAS], ignore_index=True)
            generar(transformar(crudo), salida=f"datos/bbdd_{clave}.xlsx")
        except Exception as ex:
            print(f"ERROR en {liga['nombre']}: {ex}")   # una liga caida no detiene a las demas

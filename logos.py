"""
logos.py — Escudos de equipos y logos de ligas para la web, desde ESPN (la misma fuente que espn.py usa para Liga MX).

Que hace:
  1. Por liga, pide la lista de equipos a ESPN (nombre + URL del escudo) y el logo de la liga.
  2. Empareja cada equipo de datos/bbdd_<liga>.csv con su escudo: por nombre normalizado, por alias (ALIAS) y, si no,
     por parecido. Avisa de los que no encuentra para que agregues el alias.
  3. Escribe datos/logos.json:  {"ligas": {liga: {"nombre", "logo"}}, "equipos": {liga: {nombre_bbdd: url_escudo}}}
     La API lo sirve en /logos y la web lo usa para mostrar escudos. Si un equipo no esta, la web muestra sus iniciales.

Uso: python logos.py            (una sola vez; volver a correr cuando aparezcan equipos nuevos, o dejarlo en el Action)
Nota: los escudos son marcas de cada club; para uso personal esta bien, para un producto comercial hay que licenciarlos.
"""

import difflib
import json
import re
import unicodedata

import pandas as pd
import requests

from espn import ALIAS_LIGAMX

LIGAS = {"laliga": ("esp.1", "La Liga"), "premier": ("eng.1", "Premier League"), "seriea": ("ita.1", "Serie A"),
         "bundesliga": ("ger.1", "Bundesliga"), "ligue1": ("fra.1", "Ligue 1"), "ligamx": ("mex.1", "Liga MX")}
TEAMS = "https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/teams"
SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard"
SALIDA = "datos/logos.json"

# nombre en la BBDD -> como puede llamarlo ESPN (en minusculas, sin acentos). Solo hace falta para los que no casan solos.
ALIAS = {
    # La Liga
    "Athletic Club": ["athletic club", "athletic bilbao", "athletic"], "Atletico Madrid": ["atletico madrid", "atletico de madrid"],
    "Celta de Vigo": ["celta vigo", "celta de vigo", "celta"], "Deportivo La Coruna": ["deportivo la coruna", "deportivo", "depor"],
    "Racing Santander": ["racing santander", "racing de santander", "racing"], "Real Oviedo": ["real oviedo", "oviedo"],
    "Alaves": ["alaves", "deportivo alaves"], "Espanyol": ["espanyol", "rcd espanyol"], "Mallorca": ["mallorca", "rcd mallorca"],
    "Rayo Vallecano": ["rayo vallecano", "rayo"], "Real Betis": ["real betis", "betis"], "Real Sociedad": ["real sociedad"],
    "Sevilla": ["sevilla", "sevilla fc"], "Valencia": ["valencia", "valencia cf"], "Villarreal": ["villarreal", "villarreal cf"],
    "Getafe": ["getafe", "getafe cf"], "Girona": ["girona", "girona fc"], "Levante": ["levante", "levante ud"], "Elche": ["elche", "elche cf"],
    "Malaga": ["malaga", "malaga cf"], "Osasuna": ["osasuna", "ca osasuna"], "Barcelona": ["barcelona", "fc barcelona"],
    # Premier
    "Wolverhampton": ["wolverhampton wanderers", "wolves", "wolverhampton"], "Newcastle": ["newcastle united", "newcastle"],
    "Tottenham": ["tottenham hotspur", "tottenham", "spurs"], "West Ham": ["west ham united", "west ham"],
    "Brighton": ["brighton & hove albion", "brighton and hove albion", "brighton"], "Bournemouth": ["afc bournemouth", "bournemouth"],
    "Hull": ["hull city", "hull"], "Coventry": ["coventry city", "coventry"], "Ipswich": ["ipswich town", "ipswich"],
    "Leeds United": ["leeds united", "leeds"], "Manchester City": ["manchester city", "man city"], "Manchester United": ["manchester united", "man united", "man utd"],
    "Nottingham Forest": ["nottingham forest", "nottm forest"], "Sunderland": ["sunderland"], "Burnley": ["burnley"],
    # Serie A
    "Inter": ["internazionale", "inter milan", "inter"], "AC Milan": ["ac milan", "milan"], "AS Roma": ["as roma", "roma"],
    "Hellas Verona": ["hellas verona", "verona"],
    # Bundesliga
    "FC Koln": ["fc cologne", "1. fc koln", "fc koln", "koln", "cologne"], "Borussia Monchengladbach": ["borussia monchengladbach", "monchengladbach", "gladbach"],
    "Mainz": ["1. fsv mainz 05", "mainz 05", "mainz"], "Schalke 04": ["fc schalke 04", "schalke 04", "schalke"], "St. Pauli": ["fc st. pauli", "st. pauli", "st pauli"],
    "Hamburger SV": ["hamburger sv", "hamburg", "hsv"], "Union Berlin": ["1. fc union berlin", "union berlin"], "Hoffenheim": ["tsg hoffenheim", "hoffenheim", "1899 hoffenheim"],
    "Heidenheim": ["1. fc heidenheim", "heidenheim"], "Elversberg": ["sv elversberg", "elversberg"], "Paderborn": ["sc paderborn", "sc paderborn 07", "paderborn"],
    "Werder Bremen": ["werder bremen", "sv werder bremen"], "Stuttgart": ["vfb stuttgart", "stuttgart"], "Freiburg": ["sc freiburg", "freiburg"],
    "Augsburg": ["fc augsburg", "augsburg"], "Wolfsburg": ["vfl wolfsburg", "wolfsburg"], "RB Leipzig": ["rb leipzig", "leipzig"],
    "Bayern Munich": ["bayern munich", "bayern munchen", "bayern"], "Borussia Dortmund": ["borussia dortmund", "dortmund"],
    "Bayer Leverkusen": ["bayer leverkusen", "leverkusen"], "Eintracht Frankfurt": ["eintracht frankfurt", "frankfurt"],
    # Ligue 1
    "Paris Saint-Germain": ["paris saint-germain", "paris saint germain", "psg"], "Paris FC": ["paris fc"], "Marseille": ["marseille", "olympique marseille", "olympique de marseille"],
    "Lyon": ["olympique lyonnais", "lyon"], "Lille": ["losc lille", "lille"], "Nice": ["ogc nice", "nice"], "Lens": ["rc lens", "lens"],
    "Rennes": ["stade rennais", "rennes"], "Brest": ["stade brestois", "stade brestois 29", "brest"], "Le Havre": ["le havre ac", "le havre"],
    "Monaco": ["as monaco", "monaco"], "Nantes": ["fc nantes", "nantes"], "Toulouse": ["toulouse fc", "toulouse"], "Strasbourg": ["rc strasbourg", "strasbourg", "strasbourg alsace"],
    "Angers": ["angers sco", "angers"], "Auxerre": ["aj auxerre", "auxerre"], "Lorient": ["fc lorient", "lorient"], "Metz": ["fc metz", "metz"],
    "Le Mans": ["le mans fc", "le mans"], "Troyes": ["estac troyes", "troyes"],
}
ALIAS.update(ALIAS_LIGAMX)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def equipos_csv(liga: str) -> list:
    df = pd.read_csv(f"datos/bbdd_{liga}.csv")
    return sorted(set(df.equipo_local_txt) | set(df.equipo_visitante_txt))


def equipos_espn(code: str) -> list:
    """[(nombres normalizados posibles, url del escudo)] por equipo."""
    r = requests.get(TEAMS.format(code=code), params={"limit": 200}, timeout=30); r.raise_for_status()
    out = []
    for t in r.json()["sports"][0]["leagues"][0]["teams"]:
        team = t["team"]
        nombres = {norm(team.get(k, "")) for k in ("displayName", "shortDisplayName", "name", "location", "abbreviation", "nickname")} - {""}
        logos = team.get("logos") or []
        if logos:
            out.append((nombres, logos[0]["href"], team.get("displayName")))
    return out


def logo_liga(code: str) -> str:
    try:
        r = requests.get(SCOREBOARD.format(code=code), timeout=30); r.raise_for_status()
        return r.json()["leagues"][0]["logos"][0]["href"]
    except Exception:
        return ""


def emparejar(nombre: str, espn: list):
    n = norm(nombre)
    candidatos = [n] + [norm(a) for a in ALIAS.get(nombre, [])]
    for c in candidatos:                                   # 1) nombre o alias exacto
        for nombres, url, _ in espn:
            if c in nombres:
                return url
    for nombres, url, _ in espn:                           # 2) todas las palabras del nombre estan en el de ESPN
        if any(set(n.split()) <= set(x.split()) for x in nombres):
            return url
    todos = {x: url for nombres, url, _ in espn for x in nombres}
    cerca = difflib.get_close_matches(n, list(todos), n=1, cutoff=0.85)   # 3) parecido
    return todos[cerca[0]] if cerca else None


if __name__ == "__main__":
    salida = {"ligas": {}, "equipos": {}}
    for liga, (code, nombre_liga) in LIGAS.items():
        espn = equipos_espn(code)
        salida["ligas"][liga] = {"nombre": nombre_liga, "logo": logo_liga(code)}
        salida["equipos"][liga] = {}
        faltan = []
        for eq in equipos_csv(liga):
            url = emparejar(eq, espn)
            if url:
                salida["equipos"][liga][eq] = url
            else:
                faltan.append(eq)
        print(f"{nombre_liga}: {len(salida['equipos'][liga])} escudos" + (f" · SIN ESCUDO: {faltan}" if faltan else ""))
        if faltan:
            print("   ESPN llama a sus equipos:", sorted(d for _, _, d in espn))
    json.dump(salida, open(SALIDA, "w"), ensure_ascii=False, indent=1)
    print("guardado", SALIDA)

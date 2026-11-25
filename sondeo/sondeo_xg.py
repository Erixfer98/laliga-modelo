"""Sondeo temporal (no va al PR): qué entrega FotMob (y ESPN / Sofascore) sobre xG desde GitHub Actions."""
import json
import re
import traceback

import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/131.0 Safari/537.36", "Accept-Language": "en-US,en;q=0.9"}
out = {}


def nd(html):
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>', html, re.S)
    return json.loads(m.group(1)) if m else None


def buscar(o, pat, ruta="", res=None, lim=60):
    res = [] if res is None else res
    if len(res) >= lim:
        return res
    if isinstance(o, dict):
        for k, v in o.items():
            r = f"{ruta}.{k}"
            if re.search(pat, str(k), re.I) or (isinstance(v, str) and re.search(pat, v, re.I) and len(v) < 60):
                res.append([r, json.dumps(v)[:300]])
            buscar(v, pat, r, res, lim)
    elif isinstance(o, list):
        for i, v in enumerate(o[:400]):
            buscar(v, pat, f"{ruta}[{i}]", res, lim)
    return res


def partidos(o, res=None):
    """dicts con pinta de partido: id + home + away + status."""
    res = [] if res is None else res
    if isinstance(o, dict):
        if {"id", "home", "away", "status"} <= set(o):
            res.append(o)
        else:
            for v in o.values():
                partidos(v, res)
    elif isinstance(o, list):
        for v in o:
            partidos(v, res)
    return res


def paso(nombre, f):
    try:
        out[nombre] = f()
    except Exception:
        out[nombre] = {"excepcion": traceback.format_exc()[-1500:]}


def resp(r):
    return {"status": r.status_code, "url": r.url, "tipo": r.headers.get("content-type"), "inicio": r.text[:300]}


s = requests.Session()
s.headers.update(H)

paso("api_leagues_sin_cabecera", lambda: resp(s.get("https://www.fotmob.com/api/leagues?id=87", timeout=30)))
paso("api_data_leagues", lambda: resp(s.get("https://www.fotmob.com/api/data/leagues?id=87", timeout=30)))

ESTADO = {}


def liga_html(lid, slug, extra=""):
    r = s.get(f"https://www.fotmob.com/leagues/{lid}/fixtures/{slug}{extra}", timeout=30)
    d = nd(r.text)
    info = {"status": r.status_code, "url": r.url, "next_data": d is not None,
            "titulo": (re.search(r"<title>(.*?)</title>", r.text, re.S) or [None, None])[1]}
    if d:
        pp = d.get("props", {}).get("pageProps", {})
        info["pageProps_claves"] = list(pp)[:40]
        info["temporadas"] = pp.get("allAvailableSeasons", [])[:6]
        ps = partidos(pp)
        info["n_partidos"] = len(ps)
        fin = [p for p in ps if p.get("status", {}).get("finished")]
        info["n_terminados"] = len(fin)
        info["muestra"] = fin[-2:] if fin else ps[:2]
        if fin:
            ESTADO.setdefault("match_id", fin[-1]["id"])
            ESTADO.setdefault("match_link", fin[-1].get("pageUrl"))
    return info


for lid, slug in [(87, "laliga"), (230, "liga-mx"), (42, "champions-league"), (130, "mls"), (268, "serie-a"),
                  (73, "europa-league"), (9806, "uefa-nations-league-a"), (47, "premier-league")]:
    paso(f"liga_{lid}", lambda lid=lid, slug=slug: liga_html(lid, slug))
paso("liga_87_temporada_pasada", lambda: liga_html(87, "laliga", "?season=2025%2F2026"))


def partido_html():
    mid, link = ESTADO.get("match_id"), ESTADO.get("match_link")
    info = {"match_id": mid, "link": link}
    for nombre, url in [("por_link", f"https://www.fotmob.com{link}" if link else None),
                        ("por_id", f"https://www.fotmob.com/match/{mid}")]:
        if not url:
            continue
        r = s.get(url, timeout=30)
        d = nd(r.text)
        i = {"status": r.status_code, "url": r.url, "next_data": d is not None}
        if d:
            i["xg"] = buscar(d, r"expected|xg")
            i["general"] = json.dumps(d.get("props", {}).get("pageProps", {}).get("general", {}))[:800]
            i["header"] = json.dumps(d.get("props", {}).get("pageProps", {}).get("header", {}))[:800]
        info[nombre] = i
    r = s.get(f"https://www.fotmob.com/api/matchDetails?matchId={mid}", timeout=30)
    info["api_matchDetails"] = resp(r)
    return info


paso("partido", partido_html)


def espn():
    sb = requests.get("https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/scoreboard?dates=20261122", timeout=30).json()
    ev = sb["events"][0]["id"]
    sm = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/summary?event={ev}", timeout=30).json()
    nombres = [st.get("name") for t in sm.get("boxscore", {}).get("teams", []) for st in t.get("statistics", [])]
    return {"evento": ev, "stats": nombres, "xg": buscar(sm, r"expected|xg")}


paso("espn", espn)
paso("sofascore", lambda: resp(s.get("https://api.sofascore.com/api/v1/sport/football/scheduled-events/2026-11-22", timeout=30)))

with open("sondeo/resultado.json", "w") as f:
    json.dump(out, f, indent=1, ensure_ascii=False, default=str)
print("listo")

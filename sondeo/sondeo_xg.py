"""Sondeo temporal 2 (no va al PR): formato exacto del xG en FotMob, cobertura por liga y velocidad."""
import json
import re
import time
import traceback

import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/131.0 Safari/537.36", "Accept-Language": "en-US,en;q=0.9"}
s = requests.Session()
s.headers.update(H)
out = {}

LIGAS = {"laliga": 87, "premier": 47, "seriea": 55, "bundesliga": 54, "ligue1": 53, "ligamx": 230, "champions": 42,
         "europa": 73, "brasileirao": 268, "mls": 130, "nations": 9806}


def nd(html):
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>', html, re.S)
    return json.loads(m.group(1)) if m else None


def item_xg(details):
    """El bloque de estadística 'expected_goals' del partido (Periods.All)."""
    try:
        grupos = details["content"]["stats"]["Periods"]["All"]["stats"]
    except Exception:
        return None
    for g in grupos:
        for st in g.get("stats", []):
            if st.get("key") == "expected_goals":
                return st
    return None


def ver(nombre, f):
    try:
        out[nombre] = f()
    except Exception:
        out[nombre] = {"excepcion": traceback.format_exc()[-1500:]}


def api_liga(lid, season=None):
    p = {"id": lid}
    if season:
        p["season"] = season
    r = s.get("https://www.fotmob.com/api/data/leagues", params=p, timeout=30)
    return r


ESTADO = {}


def liga(clave, lid):
    r = api_liga(lid)
    j = r.json()
    info = {"status": r.status_code, "claves": list(j)[:30], "nombre": j.get("details", {}).get("name"),
            "temporada": j.get("details", {}).get("selectedSeason"), "temporadas": j.get("allAvailableSeasons", [])[:4]}
    fx = j.get("fixtures", {})
    info["fixtures_claves"] = list(fx)[:20]
    ms = fx.get("allMatches", [])
    fin = [m for m in ms if m.get("status", {}).get("finished") and not m.get("status", {}).get("cancelled")]
    info["n"], info["n_fin"] = len(ms), len(fin)
    info["equipos"] = sorted({m["home"]["name"] for m in ms})[:40]
    info["muestra"] = fin[-1] if fin else None
    ESTADO[clave] = [m["id"] for m in fin[-3:]]
    return info


for c, l in LIGAS.items():
    ver(f"liga_{c}", lambda c=c, l=l: liga(c, l))

ver("liga_laliga_pasada", lambda: {k: v for k, v in api_liga(87, "2025/2026").json().get("details", {}).items() if k in ("name", "selectedSeason")}
    | {"n": len(api_liga(87, "2025/2026").json().get("fixtures", {}).get("allMatches", []))})
ver("liga_ligamx_clausura", lambda: {"n": len(api_liga(230, "2025/2026 - Clausura").json().get("fixtures", {}).get("allMatches", []))})


def partido_api(mid):
    r = s.get("https://www.fotmob.com/api/data/matchDetails", params={"matchId": mid}, timeout=30)
    return r


def partido_html(mid):
    r = s.get(f"https://www.fotmob.com/match/{mid}", timeout=30)
    d = nd(r.text)
    return r, (d or {}).get("props", {}).get("pageProps")


def detalle(clave):
    res = []
    for mid in ESTADO.get(clave, [])[-2:]:
        x = {"id": mid}
        t = time.time()
        r = partido_api(mid)
        x["api"] = {"status": r.status_code, "tipo": r.headers.get("content-type"), "seg": round(time.time() - t, 2)}
        det = None
        if r.status_code == 200 and "json" in (r.headers.get("content-type") or ""):
            det = r.json()
            x["api"]["claves"] = list(det)[:20]
        if det is None or item_xg(det) is None:
            t = time.time()
            rh, det2 = partido_html(mid)
            x["html"] = {"status": rh.status_code, "seg": round(time.time() - t, 2), "kb": len(rh.content) // 1024}
            det = det2 or det
        x["coverage"] = (det or {}).get("general", {}).get("coverageLevel")
        x["header_equipos"] = [(t.get("name"), t.get("score")) for t in (det or {}).get("header", {}).get("teams", [])]
        x["xg"] = item_xg(det or {})
        res.append(x)
    return res


for c in LIGAS:
    ver(f"partido_{c}", lambda c=c: detalle(c))


def velocidad():
    ids = ESTADO.get("laliga", []) + ESTADO.get("premier", []) + ESTADO.get("mls", [])
    ids = (ids * 5)[:25]
    t, est = time.time(), []
    for mid in ids:
        r = partido_api(mid)
        est.append(r.status_code)
        time.sleep(0.3)
    return {"n": len(ids), "seg": round(time.time() - t, 1), "status": est}


ver("velocidad_api", velocidad)

with open("sondeo/resultado.json", "w") as f:
    json.dump(out, f, indent=1, ensure_ascii=False, default=str)
print("listo")

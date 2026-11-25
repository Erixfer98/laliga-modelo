"""Sondeo temporal 3 (no va al PR): ids de FotMob de Nations League B, C y D."""
import json
import requests
s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"})
out = {}
for lid in list(range(9800, 9816)) + [10216, 10217, 10218]:
    try:
        j = s.get("https://www.fotmob.com/api/data/leagues", params={"id": lid}, timeout=30).json()
        ms = j.get("fixtures", {}).get("allMatches", [])
        out[lid] = [j.get("details", {}).get("name"), j.get("allAvailableSeasons", [])[:3], len(ms), sorted({m["home"]["name"] for m in ms})[:6]]
    except Exception as e:
        out[lid] = str(e)[:200]
for t in ["nations league", "Nations League B"]:
    try:
        r = s.get("https://www.fotmob.com/api/data/search/suggest", params={"term": t, "lang": "en"}, timeout=30)
        out["buscar " + t] = r.text[:3000]
    except Exception as e:
        out["buscar " + t] = str(e)[:200]
json.dump(out, open("sondeo/resultado.json", "w"), indent=1, ensure_ascii=False)

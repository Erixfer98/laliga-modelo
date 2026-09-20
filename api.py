"""
api.py — Kuota como API (FastAPI): lo mismo que muestra app.py, pero en JSON, para la pantalla nueva (web app).
No calcula nada: todo sale de kuota.py. Solo recibe parametros por URL y devuelve el paquete de cada vista.

Local:   pip install fastapi uvicorn   ->   uvicorn api:app --reload   ->   http://localhost:8000/docs (prueba interactiva)
Nube:    Render / Railway / Fly: comando de arranque  uvicorn api:app --host 0.0.0.0 --port $PORT

Rutas:
  GET  /ligas                                   ligas con datos
  GET  /liga/{liga}                             Inicio: resumen, medias, tabla, tendencias   (?tendencias=corners)
  GET  /liga/{liga}/tabla                       Tabla de posiciones                          (?temporada=2026-27)
  GET  /liga/{liga}/cara                        Cara a cara                                  ?local=..&visitante=..&solo_casa=false
  GET  /liga/{liga}/partido                     Armar + Analizar: mercados evaluados + detalle de una pata
                                                ?local=..&visitante=..&met=goles&n=5&filtro=Todos&pata=Total Over 2.5&cfg={json}
  POST /boleto   {"patas": [...], "banca": 1000} resumen del boleto + stake Kelly
  GET  /diccionario                             terminos                                     (?q=kelly)
Pendiente (necesitan claves): login de usuarios, registro de uso y el analista IA. Hoy siguen en app.py.
"""

import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import kuota

app = FastAPI(title="Kuota API", description="Poisson + Dixon-Coles para las 5 grandes ligas y Liga MX")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_cache = {}   # liga -> {"mtime", "df", "inc": {metrica: incertidumbre}}; se recarga solo si cambia el CSV (el Action lo actualiza a diario)


def datos(liga: str) -> dict:
    ruta = f"{kuota.CARPETA_DATOS}/bbdd_{liga}.csv"
    if not os.path.exists(ruta):
        raise HTTPException(404, f"liga desconocida: {liga}")
    mt = os.path.getmtime(ruta)
    if _cache.get(liga, {}).get("mtime") != mt:
        _cache[liga] = {"mtime": mt, "df": kuota.cargar(liga), "inc": {}}
    return _cache[liga]


def incert(liga: str, met: str):
    c = datos(liga)
    if met not in c["inc"]:
        c["inc"][met] = kuota.incertidumbre(c["df"], met)
    return c["inc"][met]


def validar_equipos(liga: str, *equipos: str):
    lista = kuota.equipos(datos(liga)["df"])
    for e in equipos:
        if e not in lista:
            raise HTTPException(404, f"equipo desconocido en {liga}: {e}")


@app.get("/ligas")
def ligas():
    return kuota.ligas_disponibles()


@app.get("/liga/{liga}")
def inicio(liga: str, tendencias: str = "corners"):
    return kuota.a_json(kuota.vista_inicio(datos(liga)["df"], liga, tendencias))


@app.get("/liga/{liga}/tabla")
def tabla(liga: str, temporada: str = None):
    return kuota.a_json(kuota.vista_tabla(datos(liga)["df"], liga, temporada))


@app.get("/liga/{liga}/cara")
def cara(liga: str, local: str, visitante: str, solo_casa: bool = False):
    validar_equipos(liga, local, visitante)
    return kuota.a_json(kuota.vista_cara(datos(liga)["df"], liga, local, visitante, solo_casa))


@app.get("/liga/{liga}/partido")
def partido(liga: str, local: str, visitante: str, met: str = "goles", n: int = 5, filtro: str = "Todos", pata: str = None, cfg: str = None):
    """cfg = lineas elegidas por el usuario, en JSON: {"Total": [10.5, 1], "<local>": [4.5, 1], "<visitante>": [4.5, 1]}. Sin cfg usa las de defecto."""
    validar_equipos(liga, local, visitante)
    if met not in kuota.NOM:
        raise HTTPException(404, f"metrica desconocida: {met}")
    cfg_d = json.loads(cfg) if cfg else None
    v = kuota.vista_partido(datos(liga)["df"], liga, local, visitante, met, incert(liga, met), cfg_d, n, filtro, pata)
    return kuota.a_json(v)


@app.post("/boleto")
def boleto(body: dict):
    patas, banca = body.get("patas", []), float(body.get("banca", 1000))
    return kuota.a_json({"resumen": kuota.resumen_boleto(patas), "stake": kuota.stake(patas, banca)})


@app.get("/diccionario")
def diccionario(q: str = ""):
    return kuota.diccionario(q)

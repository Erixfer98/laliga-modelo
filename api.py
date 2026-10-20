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
                                                ?local=..&visitante=..&met=goles&n=5&filtro=Todos&grupo=Total&pata=Total Over 2.5&cfg={json}
  POST /boleto   {"patas": [...], "banca": 1000} resumen del boleto + stake Kelly
  GET  /diccionario                             terminos                                     (?q=kelly)
  GET  /logos                                   escudos y logos de ligas (datos/logos.json, lo genera logos.py)
Pendiente (necesitan claves): login de usuarios, registro de uso y el analista IA. Hoy siguen en app.py.
"""

import json
import math
import os
import hashlib
from time import perf_counter
from threading import RLock, BoundedSemaphore
from cache_analisis import CacheAnalisis
import modelo
import probabilidades
from pathlib import Path

_CODIGO_ANALISIS = hashlib.sha256(b"".join(Path(__file__).with_name(p).read_bytes() for p in ("modelo.py", "probabilidades.py", "kuota.py"))).hexdigest()

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

import kuota

app = FastAPI(title="Kuota API", description="Poisson + Dixon-Coles para las 5 grandes ligas, Liga MX y Champions League")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.exception_handler(ValueError)
async def valor_invalido(request, exc):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


_cache = {}
_datos_lock = RLock()
_analisis_en_vuelo = BoundedSemaphore(2)
_modelos = CacheAnalisis(entradas=12, bytes_max=32 * 1024 * 1024)
_mercados = CacheAnalisis(entradas=512, bytes_max=16 * 1024 * 1024)
_vistas = CacheAnalisis(entradas=24, bytes_max=32 * 1024 * 1024)


def datos(liga: str) -> dict:
    if liga not in kuota.LIGAS:
        raise HTTPException(404, "liga desconocida")
    ruta = f"{kuota.CARPETA_DATOS}/bbdd_{liga}.csv"
    with _datos_lock:
        if not os.path.exists(ruta):
            raise HTTPException(404, f"liga desconocida: {liga}")
        st = os.stat(ruta)
        firma = (st.st_mtime_ns, st.st_ctime_ns, st.st_size, st.st_ino, modelo.XI)
        if _cache.get(liga, {}).get("firma") != firma:
            # Leer una única instantánea: el hash identifica exactamente el CSV analizado.
            from io import BytesIO
            for intento in range(3):
                with open(ruta, "rb") as archivo:
                    antes = os.fstat(archivo.fileno())
                    contenido = archivo.read()
                    despues = os.fstat(archivo.fileno())
                if (antes.st_mtime_ns, antes.st_ctime_ns, antes.st_size) == (despues.st_mtime_ns, despues.st_ctime_ns, despues.st_size):
                    firma = (antes.st_mtime_ns, antes.st_ctime_ns, antes.st_size, antes.st_ino, modelo.XI)
                    break
            else:
                raise HTTPException(503, "Datos actualizándose; reintenta")
            df = modelo.cargar(BytesIO(contenido))
            df.attrs["liga"] = liga
            _cache[liga] = {"firma": firma, "mtime": antes.st_mtime,
                            "version": hashlib.sha256(contenido).hexdigest(), "df": df, "inc": {}}
        return _cache[liga]


def incert(liga: str, met: str):
    with _datos_lock:
        c = datos(liga)
        return incertidumbre_snapshot(c, met)


def incertidumbre_snapshot(c, met):
    with _datos_lock:
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
def partido(liga: str, local: str, visitante: str, met: str = "goles", n: int = 5, filtro: str = "Todos", pata: str = None, cfg: str = None, grupo: str = None, modo: str = "completo", data_version: str = None):
    """Máximo dos análisis en vuelo por proceso; sin cambiar el contrato existente."""
    with _analisis_en_vuelo:
        return _partido_calculado(liga, local, visitante, met, n, filtro, pata, cfg, grupo, modo, data_version)


def _partido_calculado(liga: str, local: str, visitante: str, met: str = "goles", n: int = 5, filtro: str = "Todos", pata: str = None, cfg: str = None, grupo: str = None, modo: str = "completo", data_version: str = None):
    """cfg = lineas elegidas por el usuario, en JSON: {"Total": [10.5, 1], "<local>": [4.5, 1], "<visitante>": [4.5, 1]}. Sin cfg usa las de defecto.
    pata = mercado a detallar; si no existe, el primero del grupo (o el primero de todos)."""
    validar_equipos(liga, local, visitante)
    if met not in kuota.NOM:
        raise HTTPException(404, f"metrica desconocida: {met}")
    if local == visitante or not 1 <= n <= 80 or filtro not in ("Todos", "Como jugarán"):
        raise ValueError("equipos, n o filtro inválidos")
    cfg_d = json.loads(cfg) if cfg else None
    if cfg_d is not None and not isinstance(cfg_d, dict):
        raise ValueError("cfg debe ser un objeto")
    if modo not in ("completo", "resumen", "detalle", "version"):
        raise ValueError("modo inválido")
    inicio_t = perf_counter()
    c = datos(liga)
    if local not in kuota.equipos(c["df"]) or visitante not in kuota.equipos(c["df"]):
        raise HTTPException(404, "equipo desconocido")
    version_modelo = (_CODIGO_ANALISIS, probabilidades.VERSION, modelo.RHO, modelo.XI, tuple(sorted(modelo.K_MAX.items())), repr(modelo.METRICAS))
    version = hashlib.sha256((c["version"] + repr(version_modelo)).encode()).hexdigest()
    if data_version is not None and data_version != version:
        raise HTTPException(409, "Los datos o el modelo cambiaron; actualiza el análisis")
    if modo == "version":
        return JSONResponse({"data_version": version}, headers={"Cache-Control": "no-store"})
    inc = incertidumbre_snapshot(c, met)
    clave = (liga, c["version"], version_modelo, local, visitante, met)
    datos_t = perf_counter()
    r = _modelos.obtener(clave, lambda: modelo.analizar(c["df"], local, visitante, met, inc=inc))
    modelo_t = perf_counter()
    memo = lambda regla, calcular: _mercados.obtener((clave, json.dumps(regla, sort_keys=True)), calcular)
    preparada = _vistas.obtener((clave, json.dumps(cfg_d, sort_keys=True), n, filtro),
        lambda: kuota.preparar_partido(c["df"], local, visitante, met, inc, cfg_d, n, filtro, _modelo=r, _memo=memo))
    vista_t = perf_counter()
    v = kuota.vista_partido(c["df"], liga, local, visitante, met, inc, cfg_d, n, filtro, pata,
                           grupo=grupo, _preparado=preparada, modo=modo)
    detalle_t = perf_counter()
    convertido = {**kuota.a_json(v), "data_version": version}
    json_t = perf_counter()
    respuesta = JSONResponse(convertido)
    fin_t = perf_counter()
    tiempos = (("datos", datos_t-inicio_t), ("modelo", modelo_t-datos_t),
               ("mercados", vista_t-modelo_t), ("detalle", detalle_t-vista_t),
               ("conversion", json_t-detalle_t), ("serializacion", fin_t-json_t))
    respuesta.headers["Server-Timing"] = ", ".join(f"{nombre};dur={dur*1000:.3f}" for nombre, dur in tiempos)
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta



@app.post("/boleto")
def boleto(body: dict):
    patas = body.get("patas", [])
    if not isinstance(patas, list) or any(not isinstance(p, dict) or "cuota" not in p for p in patas):
        raise ValueError("patas debe ser una lista de selecciones con cuota")
    try:
        banca = float(body.get("banca", 1000))
    except (TypeError, ValueError) as exc:
        raise ValueError("banca inválida") from exc
    if not math.isfinite(banca) or banca <= 0:
        raise ValueError("banca debe ser finita y positiva")
    resumen = kuota.resumen_boleto(patas)
    return kuota.a_json({"resumen": resumen, "stake": kuota.stake_desde_resumen(resumen, banca)})


@app.get("/diccionario")
def diccionario(q: str = ""):
    return kuota.diccionario(q)


@app.get("/logos")
def logos():
    """Escudos por liga y equipo. Si no existe datos/logos.json (aun no corriste logos.py) devuelve vacio y la web muestra iniciales."""
    ruta = f"{kuota.CARPETA_DATOS}/logos.json"
    return json.load(open(ruta)) if os.path.exists(ruta) else {"ligas": {}, "equipos": {}}

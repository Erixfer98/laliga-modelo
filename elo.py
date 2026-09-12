"""
elo.py — Elo por metrica para Kuota. Segunda opinion junto al Poisson de modelo.py.

Un Elo por cada "duelo" del partido:
  goles -> quien gana · tiros, tiros a puerta, corners, faltas, amarillas -> que equipo hace mas.

Como funciona:
  1. Todos los equipos arrancan en 1500. Tras cada partido, el que hizo mas le quita puntos al otro.
  2. Cuanto se mueve = K x sorpresa x margen.
       sorpresa = resultado (1 / 0.5 / 0) - lo esperado segun la diferencia de Elo (con ventaja de local CASA)
       margen   = ln(1 + diferencia) / ln 2  (ganar por 3 mueve ~2 veces mas que ganar por 1; el empate no usa margen)
  3. Al cambiar de temporada cada equipo se acerca 1/3 al promedio (1500). Los que suben entran con el
     Elo promedio de los que bajaron.
  4. Elo -> probabilidad local / empate / visitante con la formula de Davidson:
       a = 10^((elo_local + CASA - elo_visitante) / 400)
       P(local) = a / (a + 1 + NU*sqrt(a))   P(empate) = NU*sqrt(a) / (...)   P(visitante) = 1 / (...)
     NU reparte el empate: cuanto mas alto, mas empates cuando los equipos son parejos.
  K, CASA y NU se ajustan por metrica sobre las 5 ligas juntas (python elo.py --ajustar) y quedan en PARAMETROS.

Uso:
  python elo.py "Real Madrid" "Barcelona"   -> Elo y probabilidades por metrica (La Liga)
  python elo.py --ajustar                    -> reajusta K, CASA y NU con datos/bbdd_*.csv e imprime el bloque PARAMETROS
  python elo.py --validar                    -> prueba fuera de muestra: Elo vs Poisson vs frecuencia base
"""

import glob
import math
import sys

import numpy as np
import pandas as pd

import modelo as mo

INICIAL = 1500.0
REGRESION = 1 / 3        # cuanto se acerca cada equipo al promedio al empezar una temporada
MIN_PJ_AJUSTE = 8        # partidos previos de cada equipo para que el partido cuente en el ajuste
UMBRAL_ALERTA = 0.10     # Poisson y Elo difieren mas que esto -> la app baja un nivel la calificacion

# metrica -> (columna local, columna visitante). El duelo es "quien hace mas".
METRICAS = {m: mo.METRICAS[m][:2] for m in ("goles", "tiros", "tiros_a_puerta", "corners", "faltas", "amarillas")}
DUELO = {"goles": "quién gana", "tiros": "más tiros", "tiros_a_puerta": "más tiros a puerta",
         "corners": "más corners", "faltas": "más faltas", "amarillas": "más amarillas"}

# Ajustado 12/09/2026 sobre las 5 ligas (temporadas 2025-26 y 2026-27). Reajustar con: python elo.py --ajustar
PARAMETROS = {
    "goles":          {"k": 40, "casa": 50, "nu": 0.75},
    "tiros":          {"k": 16, "casa": 125, "nu": 0.10},
    "tiros_a_puerta": {"k": 25, "casa": 100, "nu": 0.30},
    "corners":        {"k": 16, "casa": 100, "nu": 0.25},
    "faltas":         {"k": 12, "casa": 0, "nu": 0.15},
    "amarillas":      {"k": 16, "casa": -50, "nu": 0.60},
}


# ------------------------------------------------------------------ nucleo
def _esperado(diff: float) -> float:
    """Resultado esperado (1 = gana, 0.5 = empata, 0 = pierde) para una diferencia de Elo a favor."""
    return 1 / (1 + 10 ** (-diff / 400))


def _margen(diferencia: float) -> float:
    return max(1.0, math.log1p(diferencia) / math.log(2))


def _nueva_temporada(elo: dict, equipos: set):
    """Regresa 1/3 al promedio a los que siguen; los que suben entran con el promedio de los que bajaron."""
    if not elo:
        for e in equipos:
            elo[e] = INICIAL
        return
    salen = [e for e in elo if e not in equipos]
    entran = [e for e in equipos if e not in elo]
    base = float(np.mean([elo[e] for e in salen])) if salen else INICIAL
    for e in salen:
        del elo[e]
    for e in list(elo):
        elo[e] = INICIAL + (elo[e] - INICIAL) * (1 - REGRESION)
    for e in entran:
        elo[e] = INICIAL + (base - INICIAL) * (1 - REGRESION)


def calcular(df: pd.DataFrame, metrica: str, k: float = None, casa: float = None):
    """Recorre los partidos en orden de fecha.
    Devuelve (elo: dict equipo -> rating actual, hist: DataFrame por partido con el Elo previo de cada equipo)."""
    p = PARAMETROS.get(metrica, {"k": 20, "casa": 50, "nu": 0.5})
    k = p["k"] if k is None else k
    casa = p["casa"] if casa is None else casa
    col_l, col_v = METRICAS[metrica]
    d = df.dropna(subset=[col_l, col_v]).sort_values(["fecha", "hora_utc_txt"] if "hora_utc_txt" in df else ["fecha"], kind="stable")
    por_temp = {t: set(g.equipo_local_txt) | set(g.equipo_visitante_txt) for t, g in d.groupby("temporada_txt")}
    elo, pj, filas, temp = {}, {}, [], None
    for r in d.itertuples(index=False):
        if r.temporada_txt != temp:
            _nueva_temporada(elo, por_temp[r.temporada_txt])
            temp = r.temporada_txt
        l, v = r.equipo_local_txt, r.equipo_visitante_txt
        rl, rv = elo[l], elo[v]
        xl, xv = getattr(r, col_l), getattr(r, col_v)
        s = 1.0 if xl > xv else (0.5 if xl == xv else 0.0)
        delta = k * _margen(abs(xl - xv)) * (s - _esperado(rl + casa - rv))
        filas.append((r.fecha, temp, l, v, rl, rv, s, pj.get(l, 0), pj.get(v, 0)))
        elo[l], elo[v] = rl + delta, rv - delta
        pj[l], pj[v] = pj.get(l, 0) + 1, pj.get(v, 0) + 1
    hist = pd.DataFrame(filas, columns=["fecha", "temporada", "local", "visitante", "elo_local", "elo_visitante",
                                        "resultado", "pj_local", "pj_visitante"])
    return elo, hist


def prob(elo_l: float, elo_v: float, metrica: str) -> tuple:
    """(P local, P empate, P visitante) por Davidson, con ventaja de local y NU de la metrica."""
    p = PARAMETROS[metrica]
    a = 10 ** ((elo_l + p["casa"] - elo_v) / 400)
    s = math.sqrt(a)
    den = a + 1 + p["nu"] * s
    return a / den, p["nu"] * s / den, 1 / den


def ranking(df: pd.DataFrame, metrica: str) -> pd.DataFrame:
    """Tabla por equipo (indice = equipo): elo, delta5 (cambio en sus ultimos 5 partidos de la temporada), pj, pos."""
    elo, hist = calcular(df, metrica)
    temp = hist.temporada.iloc[-1] if len(hist) else None
    h = hist[hist.temporada == temp]
    filas = []
    for eq, r in elo.items():
        mios = h[(h.local == eq) | (h.visitante == eq)]
        if len(mios) == 0:
            ref = r
        else:
            fila = mios.iloc[-5] if len(mios) >= 5 else mios.iloc[0]          # Elo previo a su 5o partido mas reciente
            ref = fila.elo_local if fila.local == eq else fila.elo_visitante  # (o al primero de la temporada)
        filas.append({"equipo": eq, "elo": r, "delta5": r - ref, "pj": len(mios)})
    t = pd.DataFrame(filas).sort_values("elo", ascending=False).reset_index(drop=True)
    t["pos"] = np.arange(1, len(t) + 1)
    return t.set_index("equipo")


# ------------------------------------------------------------------ ajuste de K, CASA y NU
def _logverosimilitud(diff: np.ndarray, res: np.ndarray, nu: float) -> float:
    a = 10 ** (diff / 400)
    s = np.sqrt(a)
    den = a + 1 + nu * s
    p = np.where(res == 1, a / den, np.where(res == 0.5, nu * s / den, 1 / den))
    return float(np.log(np.clip(p, 1e-12, 1)).mean())


def _series(dfs: list, metrica: str, k: float, casa: float, filtro=None) -> tuple:
    """Corre el Elo liga por liga y junta (diferencia con ventaja de local, resultado) de los partidos evaluables."""
    diffs, res = [], []
    for df in dfs:
        _, h = calcular(df, metrica, k, casa)
        ok = (np.minimum(h.pj_local, h.pj_visitante) >= MIN_PJ_AJUSTE) if filtro is None else filtro(h)
        diffs.append((h.elo_local + casa - h.elo_visitante)[ok].to_numpy())
        res.append(h.resultado[ok].to_numpy())
    return np.concatenate(diffs), np.concatenate(res)


def ajustar(dfs: list, metrica: str, ks=(5, 8, 12, 16, 20, 25, 30, 40, 50), casas=range(-125, 176, 25),
            nus=np.arange(0.05, 2.01, 0.05), filtro=None) -> dict:
    """Busca en una malla los K, CASA y NU que mejor explican los partidos (maxima verosimilitud)."""
    mejor = None
    for k in ks:
        for casa in casas:
            diff, res = _series(dfs, metrica, k, casa, filtro)
            for nu in nus:
                ll = _logverosimilitud(diff, res, nu)
                if mejor is None or ll > mejor["ll"]:
                    mejor = {"k": k, "casa": casa, "nu": round(float(nu), 2), "ll": ll, "n": len(res)}
    return mejor


def cargar_ligas(patron: str = "datos/bbdd_*.csv") -> dict:
    return {ruta.split("bbdd_")[-1].replace(".csv", ""): mo.cargar(ruta) for ruta in sorted(glob.glob(patron))}


# ------------------------------------------------------------------ validacion fuera de muestra
def _poisson_1x2(df: pd.DataFrame, fecha, local: str, visitante: str, metrica: str, cache: dict):
    """1X2 del Poisson (+DC en goles) usando solo partidos anteriores a la fecha. None si falta historial."""
    clave = (fecha, metrica)
    if clave not in cache:
        prev = df[df.fecha < fecha].copy()
        prev["peso"] = np.exp(-mo.XI * (fecha - prev["fecha"]).dt.days)
        cache[clave] = mo.fuerzas(prev, metrica) if len(prev) else None
    f = cache[clave]
    if f is None or local not in f.index or visitante not in f.index:
        return None
    lam_l, lam_v = mo.lambdas(f, local, visitante)
    m = mo.matriz(lam_l, lam_v, mo.K_MAX[metrica], mo.METRICAS[metrica][2])
    return np.tril(m, -1).sum(), np.trace(m), np.triu(m, 1).sum()


def validar(ligas: dict, corte=None):
    """Ajusta K/CASA/NU solo con partidos anteriores al corte (por defecto el ultimo 1 de enero de la BBDD)
    y compara, en los partidos posteriores, la perdida logaritmica de Elo, Poisson y la frecuencia base.
    Menor = mejor. Imprime una tabla por metrica."""
    dfs = list(ligas.values())
    if corte is None:
        ult = max(df.fecha.max() for df in dfs)
        corte = pd.Timestamp(year=ult.year if ult.month >= 1 else ult.year - 1, month=1, day=1)
        if corte >= ult:
            corte = pd.Timestamp(year=ult.year - 1, month=1, day=1)
    print(f"Ajuste con partidos antes de {corte:%d/%m/%Y}; evaluacion con los posteriores (equipos con historial).")
    print(f"{'metrica':<16}{'n':>6}{'Elo':>9}{'Poisson':>9}{'base':>9}   acierto Elo / Poisson / base")
    for met in METRICAS:
        filtro = lambda h: (h.fecha < corte) & (np.minimum(h.pj_local, h.pj_visitante) >= MIN_PJ_AJUSTE)
        p = ajustar(dfs, met, filtro=filtro)
        col_l, col_v = METRICAS[met]
        ll = {"elo": [], "poisson": [], "base": []}
        acierto = {"elo": [], "poisson": [], "base": []}
        for df in dfs:
            _, h = calcular(df, met, p["k"], p["casa"])
            entren = df[df.fecha < corte]
            base = np.array([(entren[col_l] > entren[col_v]).mean(), (entren[col_l] == entren[col_v]).mean(),
                             (entren[col_l] < entren[col_v]).mean()])
            cache = {}
            for r in h[(h.fecha >= corte) & (np.minimum(h.pj_local, h.pj_visitante) >= 1)].itertuples():
                q = _poisson_1x2(df, r.fecha, r.local, r.visitante, met, cache)
                if q is None:
                    continue
                a = 10 ** ((r.elo_local + p["casa"] - r.elo_visitante) / 400)
                s = math.sqrt(a); den = a + 1 + p["nu"] * s
                pe = np.array([a / den, p["nu"] * s / den, 1 / den])
                idx = 0 if r.resultado == 1 else (1 if r.resultado == 0.5 else 2)
                for nombre, pr in (("elo", pe), ("poisson", np.array(q)), ("base", base)):
                    ll[nombre].append(-math.log(max(pr[idx], 1e-12)))
                    acierto[nombre].append(int(np.argmax(pr) == idx))
        n = len(ll["elo"])
        print(f"{met:<16}{n:>6}{np.mean(ll['elo']):>9.4f}{np.mean(ll['poisson']):>9.4f}{np.mean(ll['base']):>9.4f}   "
              f"{np.mean(acierto['elo']):.0%} / {np.mean(acierto['poisson']):.0%} / {np.mean(acierto['base']):.0%}"
              f"   (K {p['k']}, casa {p['casa']}, nu {p['nu']})")


# ------------------------------------------------------------------ CLI
if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--ajustar":
        ligas = cargar_ligas()
        print(f"Ligas: {', '.join(ligas)} · {sum(len(d) for d in ligas.values())} partidos")
        print("PARAMETROS = {")
        for met in METRICAS:
            p = ajustar(list(ligas.values()), met)
            print(f'    "{met}":{" " * (15 - len(met))}{{"k": {p["k"]}, "casa": {p["casa"]}, "nu": {p["nu"]}}},   # n={p["n"]}, logL={p["ll"]:.4f}')
        print("}")
    elif len(sys.argv) == 2 and sys.argv[1] == "--validar":
        validar(cargar_ligas())
    elif len(sys.argv) == 3:
        df = mo.cargar()
        local, visitante = sys.argv[1], sys.argv[2]
        for met in METRICAS:
            t = ranking(df, met)
            pl, px, pv = prob(t.loc[local, "elo"], t.loc[visitante, "elo"], met)
            print(f"{mo.NOMBRES[met]:<20} Elo {local} {t.loc[local, 'elo']:.0f} (#{t.loc[local, 'pos']}) · {visitante} "
                  f"{t.loc[visitante, 'elo']:.0f} (#{t.loc[visitante, 'pos']}) → {DUELO[met]}: local {pl:.0%} · empate {px:.0%} · visitante {pv:.0%}")
    else:
        sys.exit('Uso: python elo.py "Local" "Visitante" | --ajustar | --validar')

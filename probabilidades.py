"""Distribuciones y liquidaciones compartidas. No contiene lógica de interfaz.

El error por truncamiento es <= TOL_COLA antes de condicionar al soporte.
Los rangos son sensibilidad numérica; no son intervalos de confianza.
"""
import math
from itertools import product

import numpy as np
from scipy.optimize import brentq
from scipy.stats import poisson

TOL_COLA = 1e-12
MAX_K = 256
VERSION = "poisson-dc-v2"


def limite(lam, minimo=6):
    if not math.isfinite(lam) or lam < 0:
        raise ValueError("lambda debe ser finita y no negativa")
    if lam > MAX_K or not isinstance(minimo, (int, np.integer)) or not 1 <= minimo <= MAX_K:
        raise ValueError("lambda o soporte mínimo fuera de rango")
    k = max(minimo, int(poisson.isf(TOL_COLA / 2, lam))) if lam else minimo
    if k > MAX_K:
        raise ValueError("lambda excede el soporte permitido")
    return k


def distribucion(ll, lv, dc=False, rho=-0.05, k=None):
    if k is not None and (not isinstance(k, (int, np.integer)) or not 0 <= k <= MAX_K):
        raise ValueError("soporte debe ser un entero entre cero y MAX_K")
    needed = max(limite(ll), limite(lv))
    k = max(needed, k or 0)
    if k > MAX_K:
        raise ValueError("soporte demasiado grande")
    if not math.isfinite(rho):
        raise ValueError("rho no finito")
    factors = [1 - ll * lv * rho, 1 + ll * rho, 1 + lv * rho, 1 - rho]
    if dc and min(factors) < 0:
        raise ValueError("multiplicadores Dixon-Coles negativos: distribución inválida")
    xs = np.arange(k + 1)
    m = np.outer(poisson.pmf(xs, ll), poisson.pmf(xs, lv))
    if dc:
        m[0, 0] *= factors[0]
        m[0, 1] *= factors[1]
        m[1, 0] *= factors[2]
        m[1, 1] *= factors[3]
    mass = float(m.sum())
    # La corrección DC suma cero en las cuatro celdas; la cola es Poisson.
    excluded = float(poisson.sf(k, ll) + poisson.sf(k, lv)
                     - poisson.sf(k, ll) * poisson.sf(k, lv))
    if not math.isfinite(mass) or mass <= 0 or excluded > TOL_COLA:
        raise ValueError("masa probabilística inválida")
    return m / mass, {"k_max": k, "masa_excluida": excluded,
                      "tolerancia": TOL_COLA, "normalizacion": "condicionada al soporte", "version": VERSION}


def validar_linea(linea):
    if not math.isfinite(linea) or not 0 <= linea <= 100 or not float(linea * 2).is_integer():
        raise ValueError("solo se implementan líneas enteras y medias no negativas")


def validar_regla(regla):
    if not isinstance(regla, dict):
        raise ValueError("regla debe ser un objeto")
    tipo = regla.get("tipo")
    keys = {"ou": {"tipo", "lado", "linea", "over"},
            "resultado": {"tipo", "lado"}, "btts": {"tipo", "si"}}
    if not isinstance(tipo, str) or tipo not in keys or set(regla) != keys[tipo]:
        raise ValueError("liquidación no implementada o campos inválidos")
    if tipo == "ou":
        if regla["lado"] not in ("total", "local", "visitante") or not isinstance(regla["over"], bool):
            raise ValueError("lado o dirección inválidos")
        try:
            linea = float(regla["linea"])
        except (ValueError, TypeError) as exc:
            raise ValueError("línea inválida") from exc
        validar_linea(linea)
        return {**regla, "linea": linea}
    if tipo == "resultado" and regla["lado"] not in ("local", "empate", "visitante", "local_empate", "visitante_empate"):
        raise ValueError("resultado inválido")
    if tipo == "btts" and not isinstance(regla["si"], bool):
        raise ValueError("BTTS debe ser booleano")
    return dict(regla)


def liquidacion(regla, k):
    """Máscaras disjuntas de acierto/devolución. El complemento es fallo."""
    regla = validar_regla(regla)
    x, y = np.indices((k + 1, k + 1))
    tipo = regla["tipo"]
    push = np.zeros_like(x, dtype=bool)
    if tipo == "ou":
        ln = float(regla["linea"])
        validar_linea(ln)
        val = {"total": x + y, "local": x, "visitante": y}[regla["lado"]]
        win = val > ln if regla["over"] else val < ln
        push = val == ln
    elif tipo == "resultado":
        win = {"local": x > y, "empate": x == y, "visitante": x < y,
               "local_empate": x >= y, "visitante_empate": x <= y}[regla["lado"]]
    elif tipo == "btts":
        win = (x > 0) & (y > 0)
        if not regla["si"]:
            win = ~win
    else:
        raise ValueError("liquidación no implementada")
    return win, push


def prob_evento(m, mascara):
    # Solo corrige redondeo de la suma flotante, sin alterar el modelo.
    return float(np.clip(m[mascara].sum(), 0., 1.))


def retornos(m, reglas, cuotas):
    """Distribución de retorno bruto: fallo=0, devolución=1, acierto=cuota."""
    m = np.asarray(m, dtype=float)
    if (m.ndim != 2 or m.shape[0] != m.shape[1] or not m.size
            or not np.isfinite(m).all() or (m < 0).any()
            or not math.isclose(float(m.sum()), 1., rel_tol=0., abs_tol=1e-12)):
        raise ValueError("matriz probabilística inválida")
    reglas, cuotas = list(reglas), list(cuotas)
    if not reglas or len(reglas) != len(cuotas):
        raise ValueError("reglas y cuotas deben tener la misma longitud positiva")
    if any(not math.isfinite(c) or c <= 1 for c in cuotas):
        raise ValueError("cuotas deben ser finitas y mayores que uno")
    ret = np.ones(m.shape)
    allwin = np.ones(m.shape, dtype=bool)
    for regla, cuota in zip(reglas, cuotas):
        win, push = liquidacion(regla, m.shape[0] - 1)
        allwin &= win
        ret *= np.where(win, cuota, np.where(push, 1.0, 0.0))
    vals, idx = np.unique(ret, return_inverse=True)
    probs = np.bincount(idx.ravel(), weights=m.ravel(), minlength=len(vals))
    return validar_distribucion({float(v): float(p) for v, p in zip(vals, probs) if p > 0}), prob_evento(m, allwin)


def validar_distribucion(dist):
    """Valida retornos y masa; normaliza únicamente error de redondeo."""
    if not isinstance(dist, dict) or not dist:
        raise ValueError("distribución de retornos vacía o inválida")
    if any(not math.isfinite(r) or r < 0 or not math.isfinite(p) or p < 0
           for r, p in dist.items()):
        raise ValueError("retornos y probabilidades deben ser finitos y no negativos")
    mass = math.fsum(dist.values())
    if not math.isclose(mass, 1., rel_tol=0., abs_tol=1e-12):
        raise ValueError("la distribución debe sumar uno")
    return {r: p / mass for r, p in dist.items() if p > 0}


def compatibilidad(reglas, cuotas):
    """Existencia lógica de acierto total y máximo retorno, sin truncar al modelo.

    Las líneas son <=100. Todo testigo puede comprimirse a [0,102]^2:
    por encima de 100 basta conservar igualdad u orden con 101 y 102.
    Así se preservan OU, BTTS y todas las comparaciones de resultado.
    """
    reglas, cuotas = list(reglas), list(cuotas)
    if not reglas or len(reglas) != len(cuotas) or any(not math.isfinite(c) or c <= 1 for c in cuotas):
        raise ValueError("reglas o cuotas inválidas")
    x = np.ones((103, 103), dtype=bool)
    ret = np.ones(x.shape)
    for regla, cuota in zip(reglas, cuotas):
        win, push = liquidacion(regla, 102)
        x &= win
        ret *= np.where(win, cuota, np.where(push, 1., 0.))
    return bool(x.any()), float(ret.max())


def combinar(distribuciones):
    """Solo entre partidos distintos, bajo hipótesis explícita de independencia."""
    result = {1.0: 1.0}
    for dist in distribuciones:
        dist = validar_distribucion(dist)
        nuevo = {}
        for (a, p), (b, q) in product(result.items(), dist.items()):
            val = a * b
            if not math.isfinite(val):
                raise ValueError("cuota combinada fuera de rango")
            nuevo[val] = nuevo.get(val, 0.0) + p * q
        result = nuevo
        if len(result) > 100000:
            raise ValueError("demasiados escenarios de liquidación")
    return validar_distribucion(result)


def ev(dist):
    dist = validar_distribucion(dist)
    return math.fsum(p * (r - 1) for r, p in dist.items())


def kelly(dist):
    """Maximiza E[log(1+f(R-1))], f en [0,1); incluye devoluciones."""
    dist = validar_distribucion(dist)
    if ev(dist) <= 0:
        return 0.0
    cap = 1 - 1e-10
    wins = [r for r in dist if r > 1]
    if len(wins) == 1 and all(r in (0., 1., wins[0]) for r in dist):
        # Solución cerrada: evita que xtol borre stakes positivos diminutos.
        b = wins[0] - 1
        pw, pl = dist[wins[0]], dist.get(0., 0.)
        return min(cap, max(0., (pw - pl / b) / (pw + pl)))
    def derivada(f):
        return math.fsum(p * ((r - 1) / (1 + f * (r - 1))) for r, p in dist.items())
    return cap if derivada(cap) >= 0 else float(brentq(
        derivada, 0, cap, xtol=np.nextafter(0., 1.), rtol=4*np.finfo(float).eps, maxiter=2048))

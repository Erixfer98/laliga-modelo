"""
modelo_bayes.py — Segunda fuente de probabilidades: Poisson bayesiano jerárquico (+ Dixon-Coles en goles).

No toca modelo.py. De ahí importa las constantes (métricas, columnas, XI, K_MAX) y la función mercados()
para que los dos modelos calculen exactamente los mismos mercados con los mismos nombres.

Qué cambia frente a modelo.py
  · modelo.py: fuerza = promedio ponderado del equipo / promedio de la liga (4 fuerzas por equipo: casa y fuera).
  · aquí: cada equipo tiene UN ataque y UNA defensa (en escala logarítmica) que se estiman todos a la vez y
    la liga les pone un "resorte" hacia su promedio (efectos aleatorios jerárquicos): un equipo con pocos
    partidos o resultados raros queda cerca del promedio de la liga; uno con muchos partidos se aleja lo que
    digan sus datos. Cuánto pueden alejarse lo estima la propia liga (sigma_ataque, sigma_defensa).
  · la ventaja de local es un solo número por liga.
  · no sale un número por parámetro sino miles de escenarios plausibles (muestras). La probabilidad de un
    mercado es el promedio de esos escenarios y, de regalo, sale un intervalo (5%-95%).

Modelo (uno por liga y por métrica)
  log λ_local  = base + ventaja_local + ataque[local]     + defensa[visitante]
  log λ_visita = base                 + ataque[visitante] + defensa[local]
  ataque_e  ~ Normal(0, sigma_ataque)      defensa_e ~ Normal(0, sigma_defensa)    (suman cero en la liga)
  sigma_ataque, sigma_defensa ~ HalfNormal(0.5)   base ~ Normal(log promedio visitante, 1)   ventaja_local ~ Normal(0, 0.5)
  rho ~ Normal(0, 0.1)  solo en métricas con Dixon-Coles (las mismas que modelo.py: goles y goles_1t)
  Verosimilitud: Poisson(x | λ_local) · Poisson(y | λ_visita) · tau(x, y, rho), y cada partido pesa por
  recencia con el mismo exp(-XI · días) de modelo.py.

Flujo
  1. ajustar (lento, PyMC): python modelo_bayes.py ajustar laliga        -> modelos_bayes/laliga_<metrica>.npz
                            python modelo_bayes.py ajustar todas         -> las 6 ligas
     Deja también diagnosticos_bayes/<liga>_<metrica>_*.png y diagnosticos_bayes/diagnosticos.csv
  2. predecir (rápido, solo numpy): python modelo_bayes.py "Real Madrid" "Barcelona" laliga
     Desde código: cargar_modelo("laliga", "goles").analizar("Real Madrid", "Barcelona")
"""

import json
import os
import sys
import time

import numpy as np
import pandas as pd
from scipy.special import gammaln

import modelo as mo

LIGAS = ["laliga", "premier", "seriea", "bundesliga", "ligue1", "ligamx"]
CARPETA = "modelos_bayes"          # aquí quedan las muestras (.npz) que usa la predicción
CARPETA_DIAG = "diagnosticos_bayes"

PRIOR = {                          # lo que el modelo cree ANTES de ver datos (escala log)
    "sd_base": 1.0,                # base: promedio de la liga. sd 1 = muy abierta
    "mu_ventaja": 0.0, "sd_ventaja": 0.5,   # ventaja local centrada en 0: los datos deciden signo y tamaño
    "sd_sigma": 0.5,               # cuánto pueden separarse los equipos del promedio (HalfNormal)
    "sd_rho": 0.1,                 # Dixon-Coles: valores típicos -0.13 a 0
    "nu": None,                    # None = efectos Normales. Un número (ej. 4) = colas pesadas: encoge menos a los equipos extremos
}
MUESTREO = {"draws": 1000, "tune": 1000, "chains": 4, "target_accept": 0.9}
N_PRED = 1000                      # muestras usadas al predecir (las demás se descartan al guardar)
N_INTERVALO = 300                  # muestras para el intervalo de cada mercado


# ------------------------------------------------------------------ datos
def cargar_liga(liga: str, carpeta_datos: str = "datos") -> pd.DataFrame:
    """Misma carga que modelo.py (fecha + peso por recencia)."""
    return mo.cargar(os.path.join(carpeta_datos, f"bbdd_{liga}.csv"))


def preparar(df: pd.DataFrame, metrica: str) -> dict:
    """Pasa el DataFrame a los vectores que necesita el modelo: índices de equipo, conteos, pesos."""
    col_l, col_v, dixon_coles = mo.METRICAS[metrica]
    d = df.dropna(subset=[col_l, col_v]).sort_values("fecha")
    equipos = sorted(set(d["equipo_local_txt"]) | set(d["equipo_visitante_txt"]))
    idx = {e: i for i, e in enumerate(equipos)}
    return {
        "metrica": metrica, "dixon_coles": bool(dixon_coles), "equipos": equipos,
        "i_local": d["equipo_local_txt"].map(idx).to_numpy(),
        "i_visita": d["equipo_visitante_txt"].map(idx).to_numpy(),
        "x": d[col_l].to_numpy().astype(int), "y": d[col_v].to_numpy().astype(int),
        "peso": d["peso"].to_numpy().astype(float),
        "fecha_max": d["fecha"].max().strftime("%Y-%m-%d"), "n_partidos": len(d),
    }


# ------------------------------------------------------------------ modelo
def construir(datos: dict):
    """Arma el modelo PyMC. Devuelve el objeto Model (sin muestrear)."""
    import pymc as pm
    import pytensor.tensor as pt

    x, y, peso = datos["x"], datos["y"], datos["peso"]
    i_l, i_v = datos["i_local"], datos["i_visita"]
    centro_base = float(np.log(max(np.average(y, weights=peso), 0.02)))   # solo centra la previa de base

    with pm.Model(coords={"equipo": datos["equipos"]}) as modelo:
        base = pm.Normal("base", centro_base, PRIOR["sd_base"])
        ventaja = pm.Normal("ventaja_local", PRIOR["mu_ventaja"], PRIOR["sd_ventaja"])
        sigma_a = pm.HalfNormal("sigma_ataque", PRIOR["sd_sigma"])
        sigma_d = pm.HalfNormal("sigma_defensa", PRIOR["sd_sigma"])
        # parametrización "no centrada": z ~ N(0,1) y luego se escala. Muestrea mucho mejor que Normal(0, sigma) directo.
        if PRIOR["nu"]:            # colas pesadas: un Barcelona o un Real Madrid pueden alejarse más del promedio
            z_a = pm.StudentT("z_ataque", nu=PRIOR["nu"], mu=0.0, sigma=1.0, dims="equipo")
            z_d = pm.StudentT("z_defensa", nu=PRIOR["nu"], mu=0.0, sigma=1.0, dims="equipo")
        else:
            z_a = pm.Normal("z_ataque", 0.0, 1.0, dims="equipo")
            z_d = pm.Normal("z_defensa", 0.0, 1.0, dims="equipo")
        # restar la media hace que los efectos sumen cero en la liga -> base y ventaja quedan identificados
        ataque = pm.Deterministic("ataque", sigma_a * (z_a - z_a.mean()), dims="equipo")
        defensa = pm.Deterministic("defensa", sigma_d * (z_d - z_d.mean()), dims="equipo")

        lam_l = pt.exp(base + ventaja + ataque[i_l] + defensa[i_v])
        lam_v = pt.exp(base + ataque[i_v] + defensa[i_l])

        # log de Poisson(x | lam_l) + log de Poisson(y | lam_v)
        ll = x * pt.log(lam_l) - lam_l - gammaln(x + 1) + y * pt.log(lam_v) - lam_v - gammaln(y + 1)
        if datos["dixon_coles"]:
            rho = pm.Normal("rho", 0.0, PRIOR["sd_rho"])
            # misma tau que modelo.py: solo toca 0-0, 0-1, 1-0 y 1-1
            tau = pt.switch(pt.and_(pt.eq(x, 0), pt.eq(y, 0)), 1 - lam_l * lam_v * rho,
                  pt.switch(pt.and_(pt.eq(x, 0), pt.eq(y, 1)), 1 + lam_l * rho,
                  pt.switch(pt.and_(pt.eq(x, 1), pt.eq(y, 0)), 1 + lam_v * rho,
                  pt.switch(pt.and_(pt.eq(x, 1), pt.eq(y, 1)), 1 - rho, 1.0))))
            ll = ll + pt.log(pt.maximum(tau, 1e-6))
        # cada partido pesa por recencia (igual que modelo.py)
        pm.Potential("verosimilitud", pt.sum(peso * ll))
    return modelo


def muestrear(datos: dict, semilla: int = 1, **kw):
    """Corre el muestreo (NUTS). Devuelve el resultado de PyMC (posterior + estadísticas del muestreo)."""
    import pymc as pm
    opciones = {**MUESTREO, **kw}
    # cadenas en paralelo si hay núcleos (en la Mac sí; en un contenedor de 1 CPU van en serie)
    opciones.setdefault("cores", max(1, min(opciones["chains"], os.cpu_count() or 1)))
    with construir(datos):
        return pm.sample(random_seed=semilla, progressbar=False, **opciones)


def extraer(idata, datos: dict, n_pred: int = N_PRED, semilla: int = 0) -> dict:
    """Saca del posterior las muestras que hacen falta para predecir (aplanando cadenas) y recorta a n_pred."""
    post = idata.posterior
    def plano(nombre):
        v = post[nombre].values                      # (cadena, muestra, ...) -> (muestra_total, ...)
        return v.reshape((-1,) + v.shape[2:])
    m = {k: plano(k) for k in ["base", "ventaja_local", "sigma_ataque", "sigma_defensa", "ataque", "defensa"]}
    m["rho"] = plano("rho") if datos["dixon_coles"] else np.zeros_like(m["base"])
    rng = np.random.default_rng(semilla)
    sel = np.sort(rng.choice(len(m["base"]), size=min(n_pred, len(m["base"])), replace=False))
    return {k: v[sel] for k, v in m.items()}


# ------------------------------------------------------------------ ajuste completo (con diagnósticos y guardado)
def ajustar(liga: str, metrica: str, df: pd.DataFrame = None, carpeta: str = CARPETA,
            carpeta_diag: str = CARPETA_DIAG, verbose: bool = True, **kw) -> dict:
    """Ajusta una liga × métrica, corre diagnósticos, guarda el .npz y devuelve el resumen de diagnóstico."""
    import diagnosticos_bayes as dg
    df = cargar_liga(liga) if df is None else df
    datos = preparar(df, metrica)
    t0 = time.time()
    idata = muestrear(datos, **kw)
    segundos = time.time() - t0
    muestras = extraer(idata, datos)
    diag = dg.diagnosticar(idata, datos)
    diag.update({"liga": liga, "metrica": metrica, "n_partidos": datos["n_partidos"],
                 "n_equipos": len(datos["equipos"]), "segundos": round(segundos, 1)})
    dg.graficar(idata, datos, muestras, os.path.join(carpeta_diag, f"{liga}_{metrica}"))
    ppc = dg.chequeo_predictivo(muestras, datos)
    diag["ppc_fuera"] = int((~ppc["dentro"]).sum())
    guardar(muestras, datos, diag, os.path.join(carpeta, f"{liga}_{metrica}.npz"))
    ppc.to_csv(os.path.join(carpeta_diag, f"{liga}_{metrica}_ppc.csv"), index=False)
    if verbose:
        print(f"{liga:<11}{metrica:<15}{segundos:6.0f}s  {diag['veredicto']:<8} rhat {diag['rhat_max']:.3f}  "
              f"ess {diag['ess_min']:.0f}  div {diag['divergencias']}  ppc fuera {diag['ppc_fuera']}/{len(ppc)}")
    return diag


def ajustar_todo(ligas=None, metricas=None, carpeta: str = CARPETA, carpeta_diag: str = CARPETA_DIAG, **kw) -> pd.DataFrame:
    """Ajusta todas las ligas × métricas y deja diagnosticos_bayes/diagnosticos.csv con una fila por modelo."""
    ligas = LIGAS if ligas is None else ligas
    metricas = list(mo.METRICAS) if metricas is None else metricas
    os.makedirs(carpeta_diag, exist_ok=True)
    ruta = os.path.join(carpeta_diag, "diagnosticos.csv")
    columnas = ["liga", "metrica", "n_partidos", "n_equipos", "segundos", "veredicto", "motivos", "rhat_max", "ess_min",
                "divergencias", "bfmi_min", "pct_prof_max", "ppc_fuera", "base", "ventaja_local", "sigma_ataque", "sigma_defensa", "rho"]
    tabla = pd.read_csv(ruta) if os.path.exists(ruta) else pd.DataFrame(columns=columnas)
    for liga in ligas:
        df = cargar_liga(liga)
        for met in metricas:
            try:
                fila = ajustar(liga, met, df, carpeta, carpeta_diag, **kw)
            except Exception as e:           # un modelo roto no tira los demás
                print(f"ERROR {liga} {met}: {e}")
                fila = {"liga": liga, "metrica": met, "veredicto": "ERROR", "motivos": str(e)}
            fila = {k: fila.get(k) for k in columnas}
            tabla = tabla[~((tabla["liga"] == liga) & (tabla["metrica"] == met))]   # reemplaza la fila vieja
            tabla = pd.concat([tabla, pd.DataFrame([fila])], ignore_index=True)
            tabla.to_csv(ruta, index=False)                                         # se guarda tras cada modelo
    return tabla


def guardar(muestras: dict, datos: dict, diag: dict, ruta: str):
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    meta = {k: datos[k] for k in ["metrica", "dixon_coles", "equipos", "fecha_max", "n_partidos"]}
    meta["xi"], meta["diag"] = mo.XI, {k: v for k, v in diag.items() if not isinstance(v, (pd.DataFrame, pd.Series))}
    # float16 basta (error relativo < 0.2% en las λ) y deja cada archivo en ~100 KB para poder versionarlo en el repo
    np.savez_compressed(ruta, meta=json.dumps(meta, default=str),
                        **{k: v.astype(np.float16) for k, v in muestras.items()},
                        i_local=datos["i_local"], i_visita=datos["i_visita"], x=datos["x"], y=datos["y"], peso=datos["peso"])


# ------------------------------------------------------------------ predicción (solo numpy)
class ModeloBayes:
    """Muestras del posterior de una liga × métrica, listo para predecir sin PyMC."""

    def __init__(self, ruta: str):
        z = np.load(ruta)
        self.meta = json.loads(str(z["meta"]))
        self.metrica, self.dixon_coles = self.meta["metrica"], self.meta["dixon_coles"]
        self.equipos = list(self.meta["equipos"])
        self.idx = {e: i for i, e in enumerate(self.equipos)}
        self.m = {k: z[k].astype(float) for k in ["base", "ventaja_local", "sigma_ataque", "sigma_defensa", "ataque", "defensa", "rho"]}
        self.n = len(self.m["base"])

    # --- fuerzas por equipo, en la misma escala que modelo.py (1.00 = promedio de la liga)
    def fuerzas(self) -> pd.DataFrame:
        a, d = np.exp(self.m["ataque"]), np.exp(self.m["defensa"])
        return pd.DataFrame({
            "ataque": a.mean(0), "ataque_bajo": np.percentile(a, 5, axis=0), "ataque_alto": np.percentile(a, 95, axis=0),
            "defensa": d.mean(0), "defensa_bajo": np.percentile(d, 5, axis=0), "defensa_alto": np.percentile(d, 95, axis=0),
        }, index=pd.Index(self.equipos, name="equipo"))

    def _efecto(self, nombre: str, equipo: str, rng) -> np.ndarray:
        """Efecto del equipo en cada muestra. Si no está en la liga: promedio de liga con la incertidumbre de la liga."""
        if equipo in self.idx:
            return self.m[nombre][:, self.idx[equipo]]
        sigma = self.m["sigma_ataque"] if nombre == "ataque" else self.m["sigma_defensa"]
        return sigma * rng.standard_normal(self.n)

    def lambdas(self, local: str, visitante: str, semilla: int = 0) -> tuple:
        """Vectores (una λ por muestra) para local y visitante."""
        rng = np.random.default_rng(semilla)
        m = self.m
        lam_l = np.exp(m["base"] + m["ventaja_local"] + self._efecto("ataque", local, rng) + self._efecto("defensa", visitante, rng))
        lam_v = np.exp(m["base"] + self._efecto("ataque", visitante, rng) + self._efecto("defensa", local, rng))
        return lam_l, lam_v

    def analizar(self, local: str, visitante: str, lineas: list = None, n_intervalo: int = N_INTERVALO) -> dict:
        """Mismo diccionario que modelo.analizar: lambda_local, lambda_visitante, matriz, mercados, fuerzas.
        Extra: lambda_rango (5%-95%), intervalos por mercado (5%-95%) y equipos_nuevos (sin partidos en la liga)."""
        lam_l, lam_v = self.lambdas(local, visitante)
        k_max = mo.K_MAX[self.metrica]
        matrices = matrices_muestras(lam_l, lam_v, self.m["rho"], k_max, self.dixon_coles)   # (n, k+1, k+1)
        matriz = matrices.mean(axis=0)                     # promedio de escenarios = predictiva posterior
        if lineas is None:                                 # misma regla que modelo.py
            centro = round(float(lam_l.mean() + lam_v.mean()))
            lineas = [ln for ln in [centro - 1.5, centro - 0.5, centro + 0.5, centro + 1.5] if ln > 0]
        p = mo.mercados(matriz, lineas)
        paso = max(1, self.n // n_intervalo)
        por_muestra = pd.DataFrame([mo.mercados(matrices[s], lineas) for s in range(0, self.n, paso)])
        intervalos = {k: (float(por_muestra[k].quantile(0.05)), float(por_muestra[k].quantile(0.95))) for k in p}
        return {
            "metrica": self.metrica, "lambda_local": float(lam_l.mean()), "lambda_visitante": float(lam_v.mean()),
            "lambda_rango": {"lam_l": (float(np.percentile(lam_l, 5)), float(np.percentile(lam_l, 95))),
                             "lam_v": (float(np.percentile(lam_v, 5)), float(np.percentile(lam_v, 95)))},
            "matriz": matriz, "mercados": p, "intervalos": intervalos, "lineas": lineas, "fuerzas": self.fuerzas(),
            "equipos_nuevos": [e for e in (local, visitante) if e not in self.idx],
        }


def matrices_muestras(lam_l: np.ndarray, lam_v: np.ndarray, rho: np.ndarray, k_max: int, dixon_coles: bool) -> np.ndarray:
    """Una matriz de marcadores por muestra (vectorizado). Misma fórmula que modelo.matriz."""
    k = np.arange(k_max + 1)
    pl = np.exp(k * np.log(lam_l)[:, None] - lam_l[:, None] - gammaln(k + 1))   # (n, k+1)
    pv = np.exp(k * np.log(lam_v)[:, None] - lam_v[:, None] - gammaln(k + 1))
    m = pl[:, :, None] * pv[:, None, :]
    if dixon_coles:
        m[:, 0, 0] *= 1 - lam_l * lam_v * rho
        m[:, 0, 1] *= 1 + lam_l * rho
        m[:, 1, 0] *= 1 + lam_v * rho
        m[:, 1, 1] *= 1 - rho
        m = np.maximum(m, 0.0)
    return m / m.sum(axis=(1, 2), keepdims=True)


def cargar_modelo(liga: str, metrica: str, carpeta: str = CARPETA) -> ModeloBayes:
    return ModeloBayes(os.path.join(carpeta, f"{liga}_{metrica}.npz"))


def cargar_modelos(liga: str, carpeta: str = CARPETA) -> dict:
    """Todos los .npz de una liga: {metrica: ModeloBayes}. Ignora métricas sin archivo."""
    out = {}
    for met in mo.METRICAS:
        ruta = os.path.join(carpeta, f"{liga}_{met}.npz")
        if os.path.exists(ruta):
            out[met] = ModeloBayes(ruta)
    return out


# ------------------------------------------------------------------ CLI
if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "ajustar":
        ligas = LIGAS if len(args) < 2 or args[1] == "todas" else args[1:]
        tabla = ajustar_todo(ligas)
        print("\n" + tabla[["liga", "metrica", "veredicto", "rhat_max", "ess_min", "divergencias", "segundos"]].to_string(index=False))
    elif len(args) == 3:
        local, visitante, liga = args
        for met, modelo in cargar_modelos(liga).items():
            r = modelo.analizar(local, visitante)
            (a, b), (c, d) = r["lambda_rango"]["lam_l"], r["lambda_rango"]["lam_v"]
            print(f"\n{mo.NOMBRES[met]}: λ {local} = {r['lambda_local']:.2f} [{a:.2f}–{b:.2f}] | λ {visitante} = {r['lambda_visitante']:.2f} [{c:.2f}–{d:.2f}]")
            for k, v in r["mercados"].items():
                lo, hi = r["intervalos"][k]
                print(f"   {k:<24} {v:6.1%}  [{lo:5.1%}–{hi:5.1%}]   cuota justa {mo.cuota_justa(v)}")
    else:
        sys.exit('Uso: python modelo_bayes.py ajustar <liga|todas>   |   python modelo_bayes.py "Local" "Visitante" <liga>')

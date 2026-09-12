"""
modelo.py — Poisson (+ Dixon-Coles en goles) para cada par de columnas local/visitante de la BBDD.

Misma logica que el Excel modelo_poisson_dixon_coles_laliga:
  1. Cada partido pesa mas cuanto mas reciente (peso = exp(-XI * dias_atras)).
  2. Por equipo: promedio ponderado de lo que hace y lo que concede, en casa y fuera.
  3. Fuerza = promedio del equipo / promedio de la liga.
  4. lambda_local = ataque_casa(local) * defensa_fuera(visitante) * promedio_liga_casa
     lambda_visitante = ataque_fuera(visitante) * defensa_casa(local) * promedio_liga_fuera
  5. Matriz de marcadores con Poisson; en goles se aplica la correccion Dixon-Coles (rho).

Uso: python modelo.py "Real Madrid" "Barcelona"
"""

import math
import sys

import numpy as np
import pandas as pd

RUTA_DATOS = "datos/bbdd_laliga.csv"
XI = 0.005          # decaimiento por dia. 0.005 = un partido de hace 140 dias pesa la mitad
RHO = -0.05         # Dixon-Coles, solo goles. Tipico -0.03 a -0.13; 0 = Poisson puro
K_MAX = {           # tamano de la matriz por metrica (hasta cuantos eventos por equipo)
    "goles": 10, "goles_1t": 8, "goles_2t": 8,
    "tiros": 35, "tiros_a_puerta": 18, "corners": 20, "faltas": 35, "amarillas": 10, "rojas": 4,
}

# metrica -> (columna local, columna visitante, aplica Dixon-Coles)
METRICAS = {
    "goles":          ("goles_local_val", "goles_visitante_val", True),
    "goles_1t":       ("goles_local_primer_tiempo_val", "goles_visitante_primer_tiempo_val", True),
    "goles_2t":       ("goles_local_segundo_tiempo_val", "goles_visitante_segundo_tiempo_val", False),
    "tiros":          ("tiros_local_val", "tiros_visitante_val", False),
    "tiros_a_puerta": ("tiros_a_puerta_local_val", "tiros_a_puerta_visitante_val", False),
    "corners":        ("corners_local_val", "corners_visitante_val", False),
    "faltas":         ("faltas_local_val", "faltas_visitante_val", False),
    "amarillas":      ("amarillas_local_val", "amarillas_visitante_val", False),
    "rojas":          ("rojas_local_val", "rojas_visitante_val", False),
}
NOMBRES = {
    "goles": "Goles", "goles_1t": "Goles 1er tiempo", "goles_2t": "Goles 2do tiempo",
    "tiros": "Tiros", "tiros_a_puerta": "Tiros a puerta", "corners": "Corners",
    "faltas": "Faltas", "amarillas": "Tarjetas amarillas", "rojas": "Tarjetas rojas",
}


# ------------------------------------------------------------------ datos
def cargar(ruta: str = RUTA_DATOS) -> pd.DataFrame:
    df = pd.read_csv(ruta)
    df["fecha"] = pd.to_datetime(df["fecha_dt"], dayfirst=True)
    dias_atras = (df["fecha"].max() - df["fecha"]).dt.days
    df["peso"] = np.exp(-XI * dias_atras)
    return df


def equipos(df: pd.DataFrame) -> list:
    return sorted(set(df["equipo_local_txt"]) | set(df["equipo_visitante_txt"]))


# ------------------------------------------------------------------ fuerzas
def fuerzas(df: pd.DataFrame, metrica: str) -> pd.DataFrame:
    """Tabla por equipo: ataque/defensa en casa y fuera, relativos al promedio de la liga."""
    col_l, col_v, _ = METRICAS[metrica]
    d = df.dropna(subset=[col_l, col_v])
    w = d["peso"]
    prom_casa = np.average(d[col_l], weights=w)     # lo que hace un local promedio
    prom_fuera = np.average(d[col_v], weights=w)    # lo que hace un visitante promedio

    filas = []
    for eq in equipos(d):
        casa = d[d["equipo_local_txt"] == eq]
        fuera = d[d["equipo_visitante_txt"] == eq]
        wc, wf = casa["peso"], fuera["peso"]
        gf_casa = np.average(casa[col_l], weights=wc) if len(casa) else prom_casa
        gc_casa = np.average(casa[col_v], weights=wc) if len(casa) else prom_fuera
        gf_fuera = np.average(fuera[col_v], weights=wf) if len(fuera) else prom_fuera
        gc_fuera = np.average(fuera[col_l], weights=wf) if len(fuera) else prom_casa
        filas.append({
            "equipo": eq, "pj_casa": len(casa), "pj_fuera": len(fuera),
            "ataque_casa": gf_casa / prom_casa, "defensa_casa": gc_casa / prom_fuera,
            "ataque_fuera": gf_fuera / prom_fuera, "defensa_fuera": gc_fuera / prom_casa,
        })
    out = pd.DataFrame(filas).set_index("equipo")
    out.attrs["prom_casa"], out.attrs["prom_fuera"] = prom_casa, prom_fuera
    return out


def lambdas(f: pd.DataFrame, local: str, visitante: str) -> tuple:
    lam_l = f.loc[local, "ataque_casa"] * f.loc[visitante, "defensa_fuera"] * f.attrs["prom_casa"]
    lam_v = f.loc[visitante, "ataque_fuera"] * f.loc[local, "defensa_casa"] * f.attrs["prom_fuera"]
    return float(lam_l), float(lam_v)


# ------------------------------------------------------------------ matriz
def poisson(lam: float, k: int) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


def tau(x: int, y: int, lam_l: float, lam_v: float, rho: float) -> float:
    """Correccion Dixon-Coles: ajusta solo 0-0, 1-0, 0-1 y 1-1."""
    if x == 0 and y == 0:
        return 1 - lam_l * lam_v * rho
    if x == 0 and y == 1:
        return 1 + lam_l * rho
    if x == 1 and y == 0:
        return 1 + lam_v * rho
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


def matriz(lam_l: float, lam_v: float, k_max: int, dixon_coles: bool, rho: float = RHO) -> np.ndarray:
    """Matriz P(local = fila, visitante = columna), normalizada para que sume 1."""
    m = np.zeros((k_max + 1, k_max + 1))
    for x in range(k_max + 1):
        for y in range(k_max + 1):
            m[x, y] = poisson(lam_l, x) * poisson(lam_v, y)
            if dixon_coles:
                m[x, y] *= tau(x, y, lam_l, lam_v, rho)
    return m / m.sum()


# ------------------------------------------------------------------ mercados
def mercados(m: np.ndarray, lineas: list) -> dict:
    """Probabilidades a partir de la matriz. lineas = lineas over/under a evaluar (ej. 2.5)."""
    k = m.shape[0]
    tot = np.array([[x + y for y in range(k)] for x in range(k)])
    p = {
        "1 (gana local)": np.tril(m, -1).sum(),
        "X (empate)": np.trace(m),
        "2 (gana visitante)": np.triu(m, 1).sum(),
        "Ambos anotan / suman": m[1:, 1:].sum(),
    }
    for ln in lineas:
        p[f"Over {ln}"] = m[tot > ln].sum()
        p[f"Under {ln}"] = m[tot < ln].sum()
    return p


def cuota_justa(prob: float) -> float:
    return round(1 / prob, 2) if prob > 0 else float("inf")


def analizar(df: pd.DataFrame, local: str, visitante: str, metrica: str, lineas: list = None) -> dict:
    f = fuerzas(df, metrica)
    lam_l, lam_v = lambdas(f, local, visitante)
    _, _, dc = METRICAS[metrica]
    m = matriz(lam_l, lam_v, K_MAX[metrica], dc)
    if lineas is None:
        centro = round(lam_l + lam_v)
        lineas = [centro - 1.5, centro - 0.5, centro + 0.5, centro + 1.5]
        lineas = [ln for ln in lineas if ln > 0]
    p = mercados(m, lineas)
    return {"metrica": metrica, "lambda_local": lam_l, "lambda_visitante": lam_v,
            "matriz": m, "mercados": p, "fuerzas": f}


# ------------------------------------------------------------------ CLI
if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit('Uso: python modelo.py "Local" "Visitante"')
    df = cargar()
    local, visitante = sys.argv[1], sys.argv[2]
    for met in METRICAS:
        r = analizar(df, local, visitante, met)
        print(f"\n{NOMBRES[met]}: λ {local} = {r['lambda_local']:.2f} | λ {visitante} = {r['lambda_visitante']:.2f}")
        for k, v in r["mercados"].items():
            print(f"   {k:<24} {v:6.1%}   cuota justa {cuota_justa(v)}")


# ------------------------------------------------------------------ descriptivos (para la app)
def ultimos_n(df: pd.DataFrame, equipo: str, metrica: str, n: int = 10) -> pd.DataFrame:
    """Ultimos n partidos del equipo: a favor, en contra y total de la metrica."""
    col_l, col_v, _ = METRICAS[metrica]
    d = df[(df["equipo_local_txt"] == equipo) | (df["equipo_visitante_txt"] == equipo)].dropna(subset=[col_l, col_v])
    d = d.sort_values("fecha", ascending=False).head(n)
    es_local = d["equipo_local_txt"] == equipo
    out = pd.DataFrame({
        "fecha": d["fecha"].dt.strftime("%d/%m/%y"),
        "condicion": np.where(es_local, "Casa", "Fuera"),
        "rival": np.where(es_local, d["equipo_visitante_txt"], d["equipo_local_txt"]),
        "marcador": d["goles_local_val"].astype(int).astype(str) + "-" + d["goles_visitante_val"].astype(int).astype(str),
        "a_favor": np.where(es_local, d[col_l], d[col_v]).astype(int),
        "en_contra": np.where(es_local, d[col_v], d[col_l]).astype(int),
    })
    out["total"] = out["a_favor"] + out["en_contra"]
    return out.reset_index(drop=True)


def medias_liga(df: pd.DataFrame, metrica: str) -> dict:
    col_l, col_v, _ = METRICAS[metrica]
    d = df.dropna(subset=[col_l, col_v])
    return {"local": d[col_l].mean(), "visitante": d[col_v].mean(), "total": (d[col_l] + d[col_v]).mean()}


def prob_over(lam: float, linea: float, k_max: int = 60) -> float:
    """P(Poisson(lam) > linea) para lineas de un solo equipo."""
    return 1 - sum(poisson(lam, k) for k in range(int(math.floor(linea)) + 1))

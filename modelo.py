"""Modelo B + Poisson y Dixon-Coles con soporte dinámico y sensibilidad heurística.
Fuerzas (Modelo B): un ataque y una defensa por equipo con todos sus partidos, ajustados por la fuerza
de cada rival y frenados con K_ENCOGE partidos inventados de equipo promedio. Metodología y prueba:
docs/MODELO_B.md. Los rangos son sensibilidad heurística; su cobertura no está validada.
"""

import math
import sys

import numpy as np
import pandas as pd
from scipy.stats import t as t_student
from scipy.stats import poisson as poisson_dist
import probabilidades as pr

RUTA_DATOS = "datos/bbdd_laliga.csv"
XI = 0.005          # decaimiento por dia. 0.005 = un partido de hace 140 dias pesa la mitad
RHO = -0.05         # Dixon-Coles, solo goles. Tipico -0.03 a -0.13; 0 = Poisson puro
K_ENCOGE = 10       # freno del Modelo B: partidos inventados de equipo promedio que se suman a cada equipo
VUELTAS = 25        # vueltas del cálculo de fuerzas; desde la ~10 los valores ya no cambian
METRICAS_PROMEDIO = ("rojas",)   # usan el promedio de la liga: en la prueba el modelo fue peor que el promedio
CONFIANZA = 0.90    # Cuantil t usado como heurística; NO implica cobertura validada.
PJ_MIN = 5          # partidos efectivos minimos en esa condicion para fiarse del rango -> si no, "pocos datos"
CORTES_VAR = (0.8, 1.2)   # ancho relativo del equipo / mediana de la liga: < 0.8 estable, > 1.2 volatil
K_MAX = {           # soporte mínimo compatible; la cola determina el límite dinámico
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
    """Modelo B. Por equipo, un ataque y una defensa relativos a un equipo promedio (1.00 = promedio):
      ataque  = (Σ peso × anotados + F) ÷ (Σ peso × esperados a favor + F)
      defensa = (Σ peso × recibidos + F) ÷ (Σ peso × esperados en contra + F)
      esperados a favor   = promedio de la liga en la sede del equipo × defensa del rival
      esperados en contra = promedio de la liga en la sede del rival × ataque del rival
      F (freno) = K_ENCOGE × (prom_casa + prom_fuera) / 2: K partidos inventados donde el equipo hace lo esperado.
    Como cada fuerza depende de las de los rivales, se calcula en VUELTAS (vuelta 1: todas las defensas = 1).
    La ventaja de local es la de la liga (prom_casa / prom_fuera). Las métricas de METRICAS_PROMEDIO usan 1.00.
    Se conservan las columnas ataque_casa / defensa_casa / ataque_fuera / defensa_fuera (iguales a ataque y defensa)
    para que lambdas() y quienes las leen no cambien."""
    col_l, col_v, _ = METRICAS[metrica]
    d = df.dropna(subset=[col_l, col_v])
    w = d["peso"].to_numpy(dtype=float)
    vals = d[[col_l, col_v]].to_numpy(dtype=float)
    if d.empty or not np.isfinite(w).all() or (w <= 0).any():
        raise ValueError("datos o pesos insuficientes/invalidos")
    if not np.isfinite(vals).all() or (vals < 0).any() or (vals != np.floor(vals)).any():
        raise ValueError("la métrica requiere conteos enteros, finitos y no negativos")
    x, y = vals[:, 0], vals[:, 1]
    prom_casa = float(np.average(x, weights=w))     # lo que hace un local promedio
    prom_fuera = float(np.average(y, weights=w))    # lo que hace un visitante promedio
    eqs = equipos(d)
    n = len(eqs)
    pos = {e: i for i, e in enumerate(eqs)}
    il = d["equipo_local_txt"].map(pos).to_numpy()
    iv = d["equipo_visitante_txt"].map(pos).to_numpy()
    ataque, defensa = np.ones(n), np.ones(n)
    freno = K_ENCOGE * (prom_casa + prom_fuera) / 2
    if metrica not in METRICAS_PROMEDIO and prom_casa + prom_fuera > 0:
        anotados = np.bincount(il, w * x, n) + np.bincount(iv, w * y, n)
        recibidos = np.bincount(iv, w * x, n) + np.bincount(il, w * y, n)
        for _ in range(VUELTAS):
            esperados_favor = np.bincount(il, w * prom_casa * defensa[iv], n) + np.bincount(iv, w * prom_fuera * defensa[il], n)
            ataque = (anotados + freno) / (esperados_favor + freno)
            esperados_contra = np.bincount(iv, w * prom_casa * ataque[il], n) + np.bincount(il, w * prom_fuera * ataque[iv], n)
            defensa = (recibidos + freno) / (esperados_contra + freno)
        ataque = np.where(np.isfinite(ataque), ataque, 1.0)     # freno = 0 y equipo sin esperados: promedio
        defensa = np.where(np.isfinite(defensa), defensa, 1.0)
    out = pd.DataFrame({
        "equipo": eqs,
        "pj_casa": np.bincount(il, minlength=n), "pj_fuera": np.bincount(iv, minlength=n),
        "ataque": ataque, "defensa": defensa,
        "ataque_casa": ataque, "defensa_casa": defensa, "ataque_fuera": ataque, "defensa_fuera": defensa,
    }).set_index("equipo")
    out.attrs["prom_casa"], out.attrs["prom_fuera"] = prom_casa, prom_fuera
    return out


def lambdas(f: pd.DataFrame, local: str, visitante: str) -> tuple:
    if local not in f.index or visitante not in f.index:
        raise ValueError("equipo sin datos válidos para la métrica")
    lam_l = f.loc[local, "ataque_casa"] * f.loc[visitante, "defensa_fuera"] * f.attrs["prom_casa"]
    lam_v = f.loc[visitante, "ataque_fuera"] * f.loc[local, "defensa_casa"] * f.attrs["prom_fuera"]
    return float(lam_l), float(lam_v)


# ------------------------------------------------------------------ matriz
def poisson(lam: float, k: int) -> float:
    if not math.isfinite(lam) or lam < 0 or not isinstance(k, (int, np.integer)) or k < 0:
        raise ValueError("parámetros Poisson inválidos")
    return float(poisson_dist.pmf(k, lam))


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
    """k_max es un mínimo compatible; la cola determina el soporte necesario."""
    return pr.distribucion(lam_l, lam_v, dixon_coles, rho, k_max)[0]


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


def cuota_justa(prob: float, push: float = 0.0):
    if not math.isfinite(prob) or not math.isfinite(push) or not 0 <= prob <= 1 + 1e-14 or not 0 <= push <= 1 + 1e-14 or prob + push > 1 + 1e-14:
        raise ValueError("probabilidad o devolución inválida")
    if prob <= 0:
        return None
    cuota = max(prob, 1 - push) / prob
    return round(cuota, 2) if math.isfinite(cuota) else None


def analizar(df: pd.DataFrame, local: str, visitante: str, metrica: str, lineas: list = None, inc: pd.DataFrame = None) -> dict:
    f = fuerzas(df, metrica)
    lam_l, lam_v = lambdas(f, local, visitante)
    dc = METRICAS[metrica][2]
    rango = None
    if inc is not None:
        rl, tl = rango_componentes(inc, local, "casa", visitante, "fuera", lam_l, f.attrs["prom_casa"])
        rv, tv = rango_componentes(inc, visitante, "fuera", local, "casa", lam_v, f.attrs["prom_fuera"])
        # Dominio admisible de DC con rho negativo: ambas lambdas <= -1/rho.
        if dc and RHO < 0:
            rl = (rl[0], min(rl[1], -1 / RHO))
            rv = (rv[0], min(rv[1], -1 / RHO))
        k = max(pr.limite(rl[1]), pr.limite(rv[1]), K_MAX[metrica])
        # Rejilla interior y central: empate y otros eventos no son monótonos.
        puntos = sorted(set((float(a), float(b)) for a in np.linspace(*rl, 7)
                            for b in np.linspace(*rv, 7)) | {(lam_l, lam_v)})
        muestras = {point: pr.distribucion(*point, dc, RHO, k)[0] for point in puntos}
        rango = {"lam_l": rl, "lam_v": rv, "esquinas": muestras,
                 "metodo": "sensibilidad heurística en rejilla 7x7 y estimación central",
                 "cobertura_validada": False, "componentes_local": tl, "componentes_visitante": tv,
                 "dominio_dc": -1 / RHO if dc and RHO < 0 else None}
    else:
        k = K_MAX[metrica]
    m, metadata = pr.distribucion(lam_l, lam_v, dc, RHO, k)
    if lineas is None:
        centro = round(lam_l + lam_v)
        lineas = [ln for ln in (centro - 1.5, centro - .5, centro + .5, centro + 1.5) if ln > 0]
    r = {"metrica": metrica, "lambda_local": lam_l, "lambda_visitante": lam_v,
         "matriz": m, "mercados": mercados(m, lineas), "fuerzas": f, "distribucion": metadata}
    if rango is not None:
        r["rango"] = rango
    return r


# ------------------------------------------------------------------ incertidumbre de la lambda
def _inc_ofensiva(df: pd.DataFrame, metrica: str) -> pd.DataFrame:
    """Por equipo y condicion (casa / fuera), sobre lo que produce (a favor) con la misma recencia del modelo:
      n_ef   = (sum w)^2 / sum w^2   partidos efectivos
      media  = promedio ponderado      desv = desviacion ponderada (corregida por n_ef)
      mult   = t(CONFIANZA, n_ef - 1)  sube con pocos partidos, tiende a 1.28
      rel    = mult * desv / sqrt(n_ef) / media   error relativo del promedio (rango = media * (1 -+ rel))
      ancho  = 2 * rel                 ratio = ancho / mediana del ancho de la liga (equipos con n_ef >= PJ_MIN)
      estado = estable (< 0.8) · normal · volatil (> 1.2) · pocos datos (n_ef < PJ_MIN)"""
    col_l, col_v, _ = METRICAS[metrica]
    d = df.dropna(subset=[col_l, col_v])
    filas = {}
    for eq in equipos(d):
        for cond, sub, col in (("casa", d[d["equipo_local_txt"] == eq], col_l), ("fuera", d[d["equipo_visitante_txt"] == eq], col_v)):
            x, w = sub[col].values.astype(float), sub["peso"].values
            n_ef = w.sum() ** 2 / (w ** 2).sum() if len(x) else 0.0
            media = np.average(x, weights=w) if len(x) else 0.0
            desv = math.sqrt(np.average((x - media) ** 2, weights=w) * n_ef / (n_ef - 1)) if n_ef > 1.5 else float("nan")
            filas.setdefault(eq, {}).update({f"n_ef_{cond}": n_ef, f"media_{cond}": media, f"desv_{cond}": desv})
    out = pd.DataFrame.from_dict(filas, orient="index").rename_axis("equipo")
    for cond in ("casa", "fuera"):
        n_ef, media, desv = out[f"n_ef_{cond}"], out[f"media_{cond}"], out[f"desv_{cond}"]
        fiables = n_ef >= PJ_MIN
        # con pocos partidos la desviacion propia no es fiable (2 partidos iguales = desv 0): se usa la
        # dispersion tipica de la liga (mediana de desv / media de los equipos fiables) escalada a la media del equipo
        cv_liga = (desv / media)[fiables & (media > 0)].median() if (fiables & (media > 0)).any() else 1.0
        desv_uso = np.where(fiables & desv.notna(), desv, cv_liga * media)
        mult = np.where(n_ef > 1.5, t_student.ppf(CONFIANZA, np.maximum(n_ef - 1, 0.5)), np.nan)
        rel = np.where((n_ef > 1.5) & (media > 0), np.minimum(mult * desv_uso / np.sqrt(np.maximum(n_ef, 1e-9)) / np.where(media > 0, media, 1), 1.0), 1.0)
        out[f"mult_{cond}"], out[f"rel_{cond}"], out[f"ancho_{cond}"] = mult, rel, 2 * rel
        fiables = out[f"n_ef_{cond}"] >= PJ_MIN
        ref = out.loc[fiables, f"ancho_{cond}"].median() if fiables.any() else out[f"ancho_{cond}"].median()
        out[f"ratio_{cond}"] = out[f"ancho_{cond}"] / ref if ref > 0 else 1.0
        out[f"estado_{cond}"] = np.where(~fiables, "pocos datos",
                                         np.where(out[f"ratio_{cond}"] < CORTES_VAR[0], "estable",
                                                  np.where(out[f"ratio_{cond}"] > CORTES_VAR[1], "volátil", "normal")))
    return out


def incertidumbre(df: pd.DataFrame, metrica: str) -> pd.DataFrame:
    out = _inc_ofensiva(df, metrica)
    cl, cv, _ = METRICAS[metrica]
    swap = df.copy()
    swap[cl], swap[cv] = df[cv].values, df[cl].values
    defensa = _inc_ofensiva(swap, metrica)
    for col in defensa.columns:
        out["def_" + col] = defensa[col]
    return out


def rango_componentes(inc, atacante, cond_a, defensor, cond_d, lam, referencia):
    """Rango heurístico de λ centrado en la λ del modelo:
      bajo = λ × (1 − rel_ataque) × (1 − rel_defensa)      alto = λ × (1 + rel_ataque) × (1 + rel_defensa)
    rel = t de Student × desv / √n_ef / media sobre los partidos del equipo en esa condición (incertidumbre()).
    Es sensibilidad, no un intervalo de confianza validado."""
    exposicion_liga = float(inc[f"n_ef_{cond_a}"].sum())

    def componente(eq, cond, prefijo):
        row = inc.loc[eq]
        n = float(row[f"{prefijo}n_ef_{cond}"])
        rel = float(row[f"{prefijo}rel_{cond}"]) if n > 0 else 1.0
        return {"equipo": eq, "condicion": cond, "media": float(row[f"{prefijo}media_{cond}"]), "n_ef": n,
                "error_relativo": rel, "origen": "historial" if n > 0 else "sin partidos en esa condición"}
    off = componente(atacante, cond_a, "")
    deff = componente(defensor, cond_d, "def_")
    lo = lam * max(0.0, 1 - off["error_relativo"]) * max(0.0, 1 - deff["error_relativo"])
    hi = lam * (1 + off["error_relativo"]) * (1 + deff["error_relativo"])
    if lam <= 0:
        # Liga sin eventos en ese lado: límite Poisson de cero eventos como sensibilidad.
        hi = -math.log(.1) / exposicion_liga if exposicion_liga > 0 else 0.0
    return (min(lo, lam), max(hi, lam)), {"ataque": off, "defensa": deff,
            "referencia_liga": referencia, "metodo": "λ × (1 ∓ error relativo del ataque) × (1 ∓ error relativo de la defensa)"}


def rango_lambda(inc: pd.DataFrame, equipo: str, cond: str, lam: float) -> tuple:
    """Helper ofensivo legado. analizar() propaga ataque y defensa con rango_componentes."""
    rel = float(inc.loc[equipo, f"rel_{cond}"]) if equipo in inc.index else 1.0
    return max(lam * (1 - rel), 0.0), lam * (1 + rel)


# ------------------------------------------------------------------ CLI
if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit('Uso: python modelo.py "Local" "Visitante"')
    df = cargar()
    local, visitante = sys.argv[1], sys.argv[2]
    for met in METRICAS:
        inc = incertidumbre(df, met)
        r = analizar(df, local, visitante, met, inc=inc)
        (ll, lh), (vl, vh) = r["rango"]["lam_l"], r["rango"]["lam_v"]
        print(f"\n{NOMBRES[met]}: λ {local} = {r['lambda_local']:.2f} [{ll:.2f}–{lh:.2f}] {inc.loc[local, 'estado_casa']} {inc.loc[local, 'ratio_casa']:.1f}x (n_ef {inc.loc[local, 'n_ef_casa']:.0f})"
              f" | λ {visitante} = {r['lambda_visitante']:.2f} [{vl:.2f}–{vh:.2f}] {inc.loc[visitante, 'estado_fuera']} {inc.loc[visitante, 'ratio_fuera']:.1f}x (n_ef {inc.loc[visitante, 'n_ef_fuera']:.0f})")
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
    return float(poisson_dist.sf(math.floor(linea), lam))

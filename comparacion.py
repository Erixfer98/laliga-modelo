"""
comparacion.py — Pone lado a lado modelo.py (Poisson + Dixon-Coles, "actual") y modelo_bayes.py ("bayes")
mercado por mercado, marca las discrepancias mayores a un umbral y calcula el valor esperado (EV) de cada
modelo contra las cuotas de la casa. No modifica ninguno de los dos modelos.

Columnas de la tabla
  p_actual, p_bayes      probabilidad de cada modelo (mismos mercados, mismas líneas)
  bayes_lo, bayes_hi     intervalo 5%–95% del bayesiano: qué tan seguro está de su número
  dif                    p_bayes − p_actual en puntos de probabilidad. |dif| ≥ umbral -> discrepancia = True
  cuota, p_implicita     cuota de la casa y 1/cuota (lo que la casa cree, con su margen incluido)
  ev_actual, ev_bayes    p × cuota − 1: ganancia esperada por cada 1 apostado (+0.05 = +5 centavos por unidad)
  veredicto              "valor: ambos" / "valor solo actual" / "valor solo bayes" / "sin valor" / "sin cuota"

Cuotas: {metrica: {nombre_de_mercado: cuota}} con los nombres que usa modelo.mercados():
  "1 (gana local)", "X (empate)", "2 (gana visitante)", "Ambos anotan / suman", "Over 2.5", "Under 2.5", ...
  Ej.: {"goles": {"1 (gana local)": 1.95, "Over 2.5": 1.80}, "corners": {"Over 9.5": 1.90}}

Uso: python comparacion.py "Real Madrid" "Barcelona" laliga [cuotas.json] [umbral]
Desde código:
    df, modelos = mb.cargar_liga("laliga"), mb.cargar_modelos("laliga")
    tabla = comparar_partido(df, modelos, "Real Madrid", "Barcelona", cuotas, umbral=0.05)
"""

import json
import sys

import numpy as np
import pandas as pd

import modelo as mo
import modelo_bayes as mb

UMBRAL = 0.05      # discrepancia si los modelos difieren en 5 puntos de probabilidad o más
EV_MIN = 0.0       # EV mínimo para llamar "valor" a una pata (0 = cualquier EV positivo)


def _lineas_de(mercados: dict) -> list:
    """Recupera las líneas over/under que usó modelo.py, para pasarle las mismas al bayesiano."""
    return [float(k.split()[1]) for k in mercados if k.startswith("Over ")]


def comparar_metrica(df: pd.DataFrame, modelo_b: mb.ModeloBayes, local: str, visitante: str,
                     cuotas: dict = None, umbral: float = UMBRAL, lineas: list = None, ev_min: float = EV_MIN) -> pd.DataFrame:
    """Una métrica: fila por mercado con las dos probabilidades, la discrepancia y el EV contra la cuota."""
    metrica = modelo_b.metrica
    r_a = mo.analizar(df, local, visitante, metrica, lineas)
    r_b = modelo_b.analizar(local, visitante, lineas=_lineas_de(r_a["mercados"]))
    cuotas = cuotas or {}
    filas = []
    for mercado, p_a in r_a["mercados"].items():
        p_b = r_b["mercados"][mercado]
        lo, hi = r_b["intervalos"][mercado]
        c = float(cuotas.get(mercado) or np.nan)      # sin cuota -> NaN
        ev_a = p_a * c - 1 if c > 1 else np.nan
        ev_b = p_b * c - 1 if c > 1 else np.nan
        filas.append({
            "metrica": metrica, "mercado": mercado,
            "p_actual": p_a, "p_bayes": p_b, "bayes_lo": lo, "bayes_hi": hi,
            "dif": p_b - p_a, "discrepancia": abs(p_b - p_a) >= umbral,
            "cuota": c, "p_implicita": 1 / c if c > 1 else np.nan,
            "cuota_justa_actual": mo.cuota_justa(p_a), "cuota_justa_bayes": mo.cuota_justa(p_b),
            "ev_actual": ev_a, "ev_bayes": ev_b, "veredicto": _veredicto(ev_a, ev_b, ev_min),
        })
    tabla = pd.DataFrame(filas)
    tabla.attrs["lambdas"] = {"actual": (r_a["lambda_local"], r_a["lambda_visitante"]),
                              "bayes": (r_b["lambda_local"], r_b["lambda_visitante"]),
                              "bayes_rango": r_b["lambda_rango"]}
    return tabla


def _veredicto(ev_a: float, ev_b: float, ev_min: float) -> str:
    if np.isnan(ev_a):
        return "sin cuota"
    if ev_a > ev_min and ev_b > ev_min:
        return "valor: ambos"
    if ev_a > ev_min:
        return "valor solo actual"
    if ev_b > ev_min:
        return "valor solo bayes"
    return "sin valor"


def comparar_partido(df: pd.DataFrame, modelos: dict, local: str, visitante: str, cuotas: dict = None,
                     umbral: float = UMBRAL, metricas: list = None, ev_min: float = EV_MIN) -> pd.DataFrame:
    """Todas las métricas con modelo bayesiano disponible. cuotas = {metrica: {mercado: cuota}}."""
    cuotas = cuotas or {}
    metricas = [m for m in (metricas or mo.METRICAS) if m in modelos]
    partes = [comparar_metrica(df, modelos[m], local, visitante, cuotas.get(m), umbral, None, ev_min) for m in metricas]
    tabla = pd.concat(partes, ignore_index=True)
    tabla.attrs["lambdas"] = {p["metrica"].iloc[0]: p.attrs["lambdas"] for p in partes}
    return tabla


def lambdas_lado_a_lado(tabla: pd.DataFrame, local: str, visitante: str) -> pd.DataFrame:
    """Tabla resumen: λ de cada modelo por métrica (el rango 5%–95% es del bayesiano)."""
    filas = []
    for met, l in tabla.attrs.get("lambdas", {}).items():
        (a_l, a_v), (b_l, b_v) = l["actual"], l["bayes"]
        (lo_l, hi_l), (lo_v, hi_v) = l["bayes_rango"]["lam_l"], l["bayes_rango"]["lam_v"]
        filas.append({"metrica": met, f"actual {local}": a_l, f"bayes {local}": b_l, f"rango {local}": f"{lo_l:.2f}–{hi_l:.2f}",
                      f"actual {visitante}": a_v, f"bayes {visitante}": b_v, f"rango {visitante}": f"{lo_v:.2f}–{hi_v:.2f}"})
    return pd.DataFrame(filas).round(2)


def discrepancias(tabla: pd.DataFrame) -> pd.DataFrame:
    return tabla[tabla["discrepancia"]].sort_values("dif", key=abs, ascending=False)


def con_valor(tabla: pd.DataFrame) -> pd.DataFrame:
    return tabla[tabla["veredicto"].str.startswith("valor")].sort_values("ev_bayes", ascending=False)


def resumen(tabla: pd.DataFrame) -> str:
    n, d, v = len(tabla), discrepancias(tabla), con_valor(tabla)
    lineas = [f"{n} mercados comparados · {len(d)} discrepancias · {len(v)} con valor "
              f"({(v['veredicto'] == 'valor: ambos').sum()} en ambos modelos)"]
    for _, f in d.head(8).iterrows():
        lineas.append(f"  discrepancia  {f['metrica']:<14} {f['mercado']:<22} actual {f['p_actual']:5.1%}  bayes {f['p_bayes']:5.1%} "
                      f"[{f['bayes_lo']:.0%}–{f['bayes_hi']:.0%}]  dif {f['dif']:+.1%}")
    for _, f in v.iterrows():
        lineas.append(f"  {f['veredicto']:<18} {f['metrica']:<14} {f['mercado']:<22} cuota {f['cuota']:.2f}  "
                      f"EV actual {f['ev_actual']:+.1%}  EV bayes {f['ev_bayes']:+.1%}")
    return "\n".join(lineas)


def imprimir(tabla: pd.DataFrame, local: str, visitante: str):
    lam = lambdas_lado_a_lado(tabla, local, visitante)
    if len(lam):
        print("\nλ por modelo\n" + lam.to_string(index=False))
    col = ["mercado", "p_actual", "p_bayes", "bayes_lo", "bayes_hi", "dif", "discrepancia", "cuota", "ev_actual", "ev_bayes", "veredicto"]
    fmt = {c: "{:.1%}".format for c in ["p_actual", "p_bayes", "bayes_lo", "bayes_hi", "ev_actual", "ev_bayes"]}
    fmt["dif"] = "{:+.1%}".format
    for met, parte in tabla.groupby("metrica", sort=False):
        print(f"\n{mo.NOMBRES[met]}")
        print(parte[col].to_string(index=False, formatters=fmt, na_rep="-"))
    print("\n" + resumen(tabla))


# ------------------------------------------------------------------ CLI
if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) < 3:
        sys.exit('Uso: python comparacion.py "Local" "Visitante" <liga> [cuotas.json] [umbral]')
    local, visitante, liga = args[:3]
    cuotas = json.load(open(args[3])) if len(args) > 3 else None
    umbral = float(args[4]) if len(args) > 4 else UMBRAL
    df, modelos = mb.cargar_liga(liga), mb.cargar_modelos(liga)
    if not modelos:
        sys.exit(f"No hay modelos bayesianos para {liga}. Corre: python modelo_bayes.py ajustar {liga}")
    tabla = comparar_partido(df, modelos, local, visitante, cuotas, umbral)
    imprimir(tabla, local, visitante)
    tabla.to_csv(f"comparacion_{liga}_{local}_{visitante}.csv".replace(" ", "_"), index=False)

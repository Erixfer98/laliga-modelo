"""
backtest.py — Backtest walk-forward del Poisson + Dixon-Coles (modelo.py) sobre los mercados de goles.

Como funciona (igual que si Kuota se hubiera consultado la manana de cada jornada):
  1. Para cada fecha con partidos, el modelo se ajusta SOLO con los partidos anteriores a esa fecha
     (misma recencia XI de modelo.py, medida desde esa fecha). Nada del futuro entra.
  2. Se calculan las probabilidades de cada mercado de goles y se comparan con lo que paso.
  3. Calificacion = la misma de la app: 0.6 x prob. Poisson + 0.4 x cumplimiento en los ultimos 5 partidos
     de cada equipo (N_HIST).

Mercados: Total Over/Under 0.5-4.5 · Ambos anotan Si/No · Local y Visitante Over/Under 0.5-2.5 ·
          1er tiempo Total Over/Under 0.5-2.5

Uso: python backtest.py                     -> lee datos/bbdd_<liga>.csv de las 6 ligas
     python backtest.py a.xlsx b.xlsx ...    -> usa esos archivos (hoja "partidos"); la liga sale del nombre
Salida: backtest_poisson_goles.xlsx  (hojas: resumen, calibracion, calificacion, por_liga, datos, predicciones)
"""

import os
import re
import sys

import numpy as np
import pandas as pd

import modelo as mo

LIGAS = ["laliga", "premier", "seriea", "bundesliga", "ligue1", "ligamx"]
NOMBRE_LIGA = {"laliga": "La Liga", "premier": "Premier League", "seriea": "Serie A",
               "bundesliga": "Bundesliga", "ligue1": "Ligue 1", "ligamx": "Liga MX"}
LINEAS_TOTAL = [0.5, 1.5, 2.5, 3.5, 4.5]
LINEAS_EQUIPO = [0.5, 1.5, 2.5]
LINEAS_1T = [0.5, 1.5, 2.5]
N_HIST = 5                      # ultimos N partidos de cada equipo para la parte historica de la calificacion
PJ_MIN = mo.PJ_MIN              # partidos en su condicion (local en casa / visitante fuera) para "datos suficientes"
NIVELES = ((0.78, "Excelente"), (0.68, "Buena"), (0.56, "Regular"), (0.45, "Mala"), (0.0, "Pésima"))
TRAMOS = [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]


# ------------------------------------------------------------------ datos
def cargar(ruta: str) -> pd.DataFrame:
    df = pd.read_excel(ruta, sheet_name="partidos") if ruta.lower().endswith(".xlsx") else pd.read_csv(ruta)
    df["fecha"] = pd.to_datetime(df["fecha_dt"], dayfirst=True)
    return df.sort_values(["fecha", "equipo_local_txt"]).reset_index(drop=True)


def liga_de(ruta: str) -> str:
    base = os.path.basename(ruta).lower()
    for lg in LIGAS:
        if lg in base:
            return lg
    return re.sub(r"\.(xlsx|csv)$", "", base)


def lambdas_seguras(f: pd.DataFrame, local: str, visitante: str) -> tuple:
    """Como mo.lambdas, pero un equipo sin historial (recien ascendido en su 1er partido) vale promedio de liga."""
    def g(eq, col):
        return float(f.loc[eq, col]) if eq in f.index else 1.0
    lam_l = g(local, "ataque_casa") * g(visitante, "defensa_fuera") * f.attrs["prom_casa"]
    lam_v = g(visitante, "ataque_fuera") * g(local, "defensa_casa") * f.attrs["prom_fuera"]
    return lam_l, lam_v


def calificar(p: float, tasa: float) -> str:
    s = 0.6 * p + 0.4 * tasa
    for lim, txt in NIVELES:
        if s >= lim:
            return txt
    return "Pésima"


# ------------------------------------------------------------------ predicciones partido a partido
def predecir_liga(df: pd.DataFrame, liga: str) -> pd.DataFrame:
    filas = []
    for fecha in sorted(df["fecha"].unique()):
        hist = df[df["fecha"] < fecha].copy()
        if hist.empty:
            continue
        hist["peso"] = np.exp(-mo.XI * (fecha - hist["fecha"]).dt.days)
        f_g, f_1t = mo.fuerzas(hist, "goles"), mo.fuerzas(hist, "goles_1t")
        n_casa, n_fuera = hist["equipo_local_txt"].value_counts(), hist["equipo_visitante_txt"].value_counts()

        for _, p in df[df["fecha"] == fecha].iterrows():
            local, vis = p["equipo_local_txt"], p["equipo_visitante_txt"]
            gl, gv = int(p["goles_local_val"]), int(p["goles_visitante_val"])
            g1l, g1v = int(p["goles_local_primer_tiempo_val"]), int(p["goles_visitante_primer_tiempo_val"])
            lam_l, lam_v = lambdas_seguras(f_g, local, vis)
            l1, v1 = lambdas_seguras(f_1t, local, vis)
            m = mo.matriz(lam_l, lam_v, mo.K_MAX["goles"], True)
            m1 = mo.matriz(l1, v1, mo.K_MAX["goles_1t"], True)
            k = m.shape[0]; tot = np.add.outer(np.arange(k), np.arange(k))
            k1 = m1.shape[0]; tot1 = np.add.outer(np.arange(k1), np.arange(k1))
            # historico reciente de cada equipo (cualquier condicion), como lo usa la calificacion de la app
            hl, hv = mo.ultimos_n(hist, local, "goles", N_HIST), mo.ultimos_n(hist, vis, "goles", N_HIST)
            hl1, hv1 = mo.ultimos_n(hist, local, "goles_1t", N_HIST), mo.ultimos_n(hist, vis, "goles_1t", N_HIST)
            nh = len(hl) + len(hv)

            base = {"liga": NOMBRE_LIGA.get(liga, liga), "temporada": p["temporada_txt"], "jornada": p["jornada_val"],
                    "fecha": fecha, "local": local, "visitante": vis, "goles_local": gl, "goles_visitante": gv,
                    "goles_total": gl + gv, "goles_1t_total": g1l + g1v,
                    "lambda_local": lam_l, "lambda_visitante": lam_v, "lambda_total": lam_l + lam_v,
                    "lambda_1t_total": l1 + v1,
                    "pj_casa_local": int(n_casa.get(local, 0)), "pj_fuera_visitante": int(n_fuera.get(vis, 0))}
            base["datos_suficientes"] = base["pj_casa_local"] >= PJ_MIN and base["pj_fuera_visitante"] >= PJ_MIN

            def add(grupo, mercado, linea, lado, prob, cumple_l, cumple_v, acierto):
                tasa = (cumple_l.sum() + cumple_v.sum()) / nh if nh else 0.0
                prob = float(min(max(prob, 0.0), 1.0))
                filas.append({**base, "grupo": grupo, "mercado": mercado, "linea": linea, "lado": lado,
                              "prob_poisson": prob, "tasa_ult5": float(tasa), "calificacion": calificar(prob, tasa),
                              "acierto": int(acierto)})

            for ln in LINEAS_TOTAL:
                po = m[tot > ln].sum()
                add("Total goles", f"Total Over {ln}", ln, "Over", po, hl.total > ln, hv.total > ln, gl + gv > ln)
                add("Total goles", f"Total Under {ln}", ln, "Under", 1 - po, hl.total < ln, hv.total < ln, gl + gv < ln)
            pb = m[1:, 1:].sum()
            bl, bv = (hl.a_favor > 0) & (hl.en_contra > 0), (hv.a_favor > 0) & (hv.en_contra > 0)
            add("Ambos anotan", "Ambos anotan: Sí", 0.5, "Over", pb, bl, bv, gl > 0 and gv > 0)
            add("Ambos anotan", "Ambos anotan: No", 0.5, "Under", 1 - pb, ~bl, ~bv, gl == 0 or gv == 0)
            for ln in LINEAS_EQUIPO:
                po = mo.prob_over(lam_l, ln)
                add("Goles local", f"Local Over {ln}", ln, "Over", po, hl.a_favor > ln, hv.en_contra > ln, gl > ln)
                add("Goles local", f"Local Under {ln}", ln, "Under", 1 - po, hl.a_favor < ln, hv.en_contra < ln, gl < ln)
                po = mo.prob_over(lam_v, ln)
                add("Goles visitante", f"Visitante Over {ln}", ln, "Over", po, hl.en_contra > ln, hv.a_favor > ln, gv > ln)
                add("Goles visitante", f"Visitante Under {ln}", ln, "Under", 1 - po, hl.en_contra < ln, hv.a_favor < ln, gv < ln)
            for ln in LINEAS_1T:
                po = m1[tot1 > ln].sum()
                add("1er tiempo", f"1T Total Over {ln}", ln, "Over", po, hl1.total > ln, hv1.total > ln, g1l + g1v > ln)
                add("1er tiempo", f"1T Total Under {ln}", ln, "Under", 1 - po, hl1.total < ln, hv1.total < ln, g1l + g1v < ln)
    return pd.DataFrame(filas)


# ------------------------------------------------------------------ resumenes
def picks(pred: pd.DataFrame) -> pd.DataFrame:
    """Una fila por partido y linea: el lado que el modelo prefiere (prob >= 50%)."""
    over = pred[pred["lado"] == "Over"].copy()
    over["pick"] = np.where(over["prob_poisson"] >= 0.5, "Over", "Under")
    over["prob_pick"] = np.where(over["pick"] == "Over", over["prob_poisson"], 1 - over["prob_poisson"])
    over["acierto_pick"] = np.where(over["pick"] == "Over", over["acierto"], 1 - over["acierto"])
    over["ocurrio_over"] = over["acierto"]
    over["mercado"] = over["mercado"].str.replace(" Over ", " ", regex=False).str.replace(": Sí", "", regex=False)
    return over


def ingenuo(g: pd.DataFrame) -> float:
    """Acierto de apostar siempre al lado mas frecuente de cada linea en cada liga (sin modelo)."""
    if len(g) == 0:
        return np.nan
    hits = sum(max(s.sum(), len(s) - s.sum()) for _, s in g.groupby(["liga", "mercado"])["ocurrio_over"])
    return hits / len(g)


def resumen_mercados(pk: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for (grupo, mercado), g in pk.groupby(["grupo", "mercado"], sort=False):
        base = g["ocurrio_over"].mean()
        filas.append({
            "grupo": grupo, "mercado": mercado, "partidos": len(g),
            "over_real_pct": base,
            "pct_picks_over": (g["pick"] == "Over").mean(),
            "acierto_modelo": g["acierto_pick"].mean(),
            "acierto_sin_modelo": ingenuo(g),
            "prob_media_pick": g["prob_pick"].mean(),
            "brier_modelo": ((g["prob_poisson"] - g["ocurrio_over"]) ** 2).mean(),
            "brier_sin_modelo": ((base - g["ocurrio_over"]) ** 2).mean(),
        })
    r = pd.DataFrame(filas)
    r["mejora_vs_sin_modelo"] = r["acierto_modelo"] - r["acierto_sin_modelo"]
    r["habilidad_brier"] = 1 - r["brier_modelo"] / r["brier_sin_modelo"]
    return r


def calibracion(pk: pd.DataFrame, por: str = None) -> pd.DataFrame:
    filas = []
    grupos = [(None, pk)] if por is None else list(pk.groupby(por, sort=False))
    for nombre, g in grupos:
        for lo, hi in TRAMOS:
            s = g[(g["prob_pick"] >= lo) & (g["prob_pick"] < hi)]
            if len(s) == 0:
                continue
            filas.append({**({por: nombre} if por else {}),
                          "tramo_prob": f"{lo:.0%}–{min(hi, 1):.0%}", "picks": len(s),
                          "prob_media": s["prob_pick"].mean(), "acierto_real": s["acierto_pick"].mean()})
    r = pd.DataFrame(filas)
    r["diferencia"] = r["acierto_real"] - r["prob_media"]
    return r


def por_calificacion(pred: pd.DataFrame) -> pd.DataFrame:
    orden = [t for _, t in NIVELES]
    filas = []
    for cal, g in pred.groupby("calificacion"):
        filas.append({"calificacion": cal, "patas": len(g), "prob_poisson_media": g["prob_poisson"].mean(),
                      "acierto_real": g["acierto"].mean(),
                      "cuota_justa_modelo": 1 / g["prob_poisson"].mean(),
                      "cuota_minima_rentable": 1 / g["acierto"].mean() if g["acierto"].mean() > 0 else np.nan})
    r = pd.DataFrame(filas)
    r["calificacion"] = pd.Categorical(r["calificacion"], orden, ordered=True)
    return r.sort_values("calificacion").reset_index(drop=True)


def por_liga(pk: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for (liga, temporada), g in pk.groupby(["liga", "temporada"], sort=False):
        t25 = g[g["mercado"] == "Total 2.5"]
        filas.append({"liga": liga, "temporada": temporada, "partidos": t25.shape[0],
                      "acierto_todas_lineas": g["acierto_pick"].mean(), "sin_modelo_todas_lineas": ingenuo(g),
                      "acierto_total_2_5": t25["acierto_pick"].mean(), "sin_modelo_total_2_5": ingenuo(t25),
                      "prob_media_pick": g["prob_pick"].mean()})
    r = pd.DataFrame(filas)
    r["mejora_todas"] = r["acierto_todas_lineas"] - r["sin_modelo_todas_lineas"]
    r["mejora_total_2_5"] = r["acierto_total_2_5"] - r["sin_modelo_total_2_5"]
    return r


def regla_lambda(pk: pd.DataFrame) -> pd.DataFrame:
    """Regla intuitiva 'si el modelo espera 3 goles apuesto Over 2.5' (lambda total > linea) vs la regla de
    probabilidad (>= 50%). Solo lineas de total."""
    t = pk[pk["grupo"] == "Total goles"].copy()
    t["pick_lambda"] = np.where(t["lambda_total"] > t["linea"], "Over", "Under")
    t["acierto_lambda"] = np.where(t["pick_lambda"] == "Over", t["ocurrio_over"], 1 - t["ocurrio_over"])
    filas = []
    for mercado, g in t.groupby("mercado", sort=False):
        filas.append({"mercado": mercado, "partidos": len(g),
                      "acierto_regla_probabilidad": g["acierto_pick"].mean(),
                      "acierto_regla_lambda": g["acierto_lambda"].mean(),
                      "partidos_donde_difieren": int((g["pick"] != g["pick_lambda"]).sum()),
                      "acierto_prob_cuando_difieren": g.loc[g["pick"] != g["pick_lambda"], "acierto_pick"].mean()})
    return pd.DataFrame(filas)


# ------------------------------------------------------------------ excel
def escribir_excel(ruta: str, hojas: dict, notas: dict):
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    pct = {"over_real_pct", "pct_picks_over", "acierto_modelo", "acierto_sin_modelo", "prob_media_pick",
           "mejora_vs_sin_modelo", "habilidad_brier", "prob_media", "acierto_real", "diferencia",
           "prob_poisson_media", "acierto_todas_lineas", "sin_modelo_todas_lineas", "acierto_total_2_5",
           "sin_modelo_total_2_5", "mejora_todas", "mejora_total_2_5", "acierto_regla_probabilidad",
           "acierto_regla_lambda", "acierto_prob_cuando_difieren", "prob_poisson", "tasa_ult5", "acierto_pct"}
    with pd.ExcelWriter(ruta, engine="openpyxl") as xw:
        for nombre, df in hojas.items():
            df = df.copy()
            if "fecha" in df.columns:
                df["fecha"] = pd.to_datetime(df["fecha"]).dt.strftime("%d/%m/%Y")
            df.to_excel(xw, sheet_name=nombre, index=False, startrow=2)
            ws = xw.sheets[nombre]
            ws["A1"] = notas.get(nombre, "")
            ws["A1"].font = Font(name="Arial", size=10, italic=True)
            for row in ws.iter_rows(min_row=3, max_row=ws.max_row):
                for c in row:
                    c.font = Font(name="Arial", size=10, bold=(c.row == 3))
                    if c.row == 3:
                        c.fill = PatternFill("solid", fgColor="DDEBF7")
                        c.alignment = Alignment(wrap_text=True, vertical="center")
            for j, col in enumerate(df.columns, start=1):
                letra = get_column_letter(j)
                if col in pct:
                    for c in ws[letra][3:]:
                        c.number_format = "0.0%"
                elif df[col].dtype.kind == "f":
                    for c in ws[letra][3:]:
                        c.number_format = "0.00"
                ancho = max(len(str(col)), *(len(str(v)) for v in df[col].head(200))) if len(df) else len(str(col))
                ws.column_dimensions[letra].width = min(max(10, ancho + 2), 28)
            ws.freeze_panes = "A4"


# ------------------------------------------------------------------ main
def correr(rutas: list) -> dict:
    partes = []
    for ruta in rutas:
        lg = liga_de(ruta)
        df = cargar(ruta)
        p = predecir_liga(df, lg)
        print(f"{NOMBRE_LIGA.get(lg, lg):<15} {df.shape[0]:>4} partidos -> {p['fecha'].nunique():>3} fechas evaluadas, "
              f"{p.drop_duplicates(['fecha', 'local', 'visitante']).shape[0]:>4} partidos con prediccion")
        partes.append(p)
    pred = pd.concat(partes, ignore_index=True)
    ok = pred[pred["datos_suficientes"]]
    pk_ok, pk_all = picks(ok), picks(pred)

    def fila_datos(nombre, g):
        return {"grupo_datos": nombre, "partidos": g.drop_duplicates(["liga", "fecha", "local", "visitante"]).shape[0],
                "acierto_modelo": g["acierto_pick"].mean(), "acierto_sin_modelo": ingenuo(g),
                "prob_media_pick": g["prob_pick"].mean()}
    datos = pd.DataFrame([
        fila_datos("Ambos equipos con ≥ 5 partidos en su condición (usado en resumen)", pk_ok),
        fila_datos("Algún equipo con < 5 partidos en su condición (pocos datos)", pk_all[~pk_all["datos_suficientes"]]),
        fila_datos("Todos", pk_all),
    ])
    return {"pred": pred, "ok": ok, "pk_ok": pk_ok, "pk_all": pk_all,
            "resumen": resumen_mercados(pk_ok), "calibracion": calibracion(pk_ok),
            "calibracion_grupo": calibracion(pk_ok, "grupo"), "calificacion": por_calificacion(ok),
            "por_liga": por_liga(pk_ok), "regla_lambda": regla_lambda(pk_ok), "datos": datos}


if __name__ == "__main__":
    rutas = sys.argv[1:] or [f"datos/bbdd_{lg}.csv" for lg in LIGAS]
    r = correr(rutas)
    notas = {
        "resumen": "Una fila por línea. El modelo 'elige' el lado con probabilidad ≥ 50%. acierto_sin_modelo = apostar siempre al lado más frecuente de cada liga. habilidad_brier > 0 = el modelo mejora al promedio de liga. Solo partidos con ≥ 5 partidos en su condición para ambos equipos.",
        "calibracion": "Picks agrupados por la probabilidad que dio el modelo. Si prob_media ≈ acierto_real el modelo está calibrado (sus porcentajes son creíbles como cuota justa).",
        "calibracion_grupo": "Lo mismo que calibracion, por familia de mercado.",
        "calificacion": "Todas las patas (Over y Under) según la calificación de Kuota (0.6 × Poisson + 0.4 × últimos 5 de cada equipo). cuota_minima_rentable = 1 / acierto real: a partir de esa cuota la pata fue rentable en el histórico.",
        "por_liga": "Acierto del modelo vs. sin modelo por liga y temporada.",
        "regla_lambda": "Regla 'espera 3 goles → Over 2.5' (λ total > línea) frente a la regla de probabilidad ≥ 50%. Difieren cuando λ queda apenas encima de la línea (ej. 2.6): la mediana de Poisson es menor que la media.",
        "datos": "Efecto de la cantidad de datos: el modelo calculado con pocos partidos de un equipo (recién ascendidos, inicio de temporada).",
        "predicciones": "Una fila por partido, mercado y lado. prob_poisson = probabilidad del modelo calculada solo con partidos anteriores a la fecha. acierto = 1 si la pata ganó. datos_suficientes = ambos equipos con ≥ 5 partidos en su condición.",
    }
    hojas = {"resumen": r["resumen"], "calibracion": r["calibracion"], "calibracion_grupo": r["calibracion_grupo"],
             "calificacion": r["calificacion"], "por_liga": r["por_liga"], "regla_lambda": r["regla_lambda"],
             "datos": r["datos"], "predicciones": r["pred"]}
    salida = "backtest_poisson_goles.xlsx"
    escribir_excel(salida, hojas, notas)
    print(f"\nEscrito {salida}")
    pd.set_option("display.width", 200)
    print(r["resumen"][["mercado", "partidos", "over_real_pct", "acierto_modelo", "acierto_sin_modelo", "mejora_vs_sin_modelo", "prob_media_pick", "habilidad_brier"]].to_string(index=False))
    print(r["calibracion"].to_string(index=False))
    print(r["calificacion"].to_string(index=False))

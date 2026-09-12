"""
validar_bbdd.py — revisa la integridad de datos/bbdd_<liga>.csv despues de generarlos.

Errores (detienen el Action, los datos malos no se publican):
  - celdas vacias en fecha, equipos o goles finales
  - partidos duplicados (misma fecha + mismo local)
  - valores imposibles: goles al descanso > goles finales, tiros a puerta > tiros, negativos
Avisos (se publican igual, pero quedan en el reporte):
  - celdas vacias en estadisticas (tiros, corners, faltas, tarjetas, descanso)
  - ultimo partido con mas de 10 dias de antiguedad (posible fuente detenida)

Escribe datos/validacion.json (lo lee la app en Admin) y termina con codigo 1 si hay errores.
Uso: python validar_bbdd.py
"""

import glob
import json
import sys
from datetime import datetime

import pandas as pd

CLAVE = ["fecha_dt", "equipo_local_txt", "equipo_visitante_txt", "goles_local_val", "goles_visitante_val"]
ESTAD = ["goles_local_primer_tiempo_val", "goles_visitante_primer_tiempo_val", "tiros_local_val", "tiros_visitante_val",
         "tiros_a_puerta_local_val", "tiros_a_puerta_visitante_val", "corners_local_val", "corners_visitante_val",
         "faltas_local_val", "faltas_visitante_val", "amarillas_local_val", "amarillas_visitante_val",
         "rojas_local_val", "rojas_visitante_val"]


def validar(ruta: str) -> dict:
    d = pd.read_csv(ruta)
    errores, avisos = [], []

    faltan = [c for c in CLAVE + ESTAD if c not in d.columns]
    if faltan:
        return {"partidos": len(d), "errores": [f"faltan columnas: {faltan}"], "avisos": [], "vacias": 0, "ok": False}

    v_clave = int(d[CLAVE].isna().sum().sum())
    if v_clave:
        errores.append(f"{v_clave} celdas vacias en fecha/equipos/goles")

    dup = d.duplicated(["fecha_dt", "equipo_local_txt"]).sum()
    if dup:
        errores.append(f"{int(dup)} partidos duplicados")

    def malos(cond, txt):
        n = int(cond.sum())
        if n:
            filas = d[cond].head(3)
            ej = "; ".join(f"{r.fecha_dt} {r.equipo_local_txt}-{r.equipo_visitante_txt}" for _, r in filas.iterrows())
            errores.append(f"{n} partidos con {txt} (ej. {ej})")

    malos(d["goles_local_primer_tiempo_val"] > d["goles_local_val"], "goles local al descanso mayores al final")
    malos(d["goles_visitante_primer_tiempo_val"] > d["goles_visitante_val"], "goles visitante al descanso mayores al final")
    malos(d["tiros_a_puerta_local_val"] > d["tiros_local_val"], "tiros a puerta local mayores a tiros")
    malos(d["tiros_a_puerta_visitante_val"] > d["tiros_visitante_val"], "tiros a puerta visitante mayores a tiros")
    malos((d[CLAVE[3:] + ESTAD] < 0).any(axis=1), "valores negativos")

    vacias = d[ESTAD].isna()
    n_vacias = int(vacias.sum().sum())
    if n_vacias:
        filas = d[vacias.any(axis=1)]
        ej = "; ".join(f"{r.fecha_dt} {r.equipo_local_txt}-{r.equipo_visitante_txt}" for _, r in filas.head(3).iterrows())
        avisos.append(f"{n_vacias} celdas de estadisticas vacias en {len(filas)} partidos (ej. {ej})")

    ultimo = pd.to_datetime(d["fecha_dt"], dayfirst=True).max()
    dias = (datetime.now() - ultimo).days
    if dias > 10:
        avisos.append(f"ultimo partido hace {dias} dias ({ultimo:%d/%m/%Y}); revisar si la fuente dejo de actualizar")

    return {"partidos": len(d), "ultimo": f"{ultimo:%d/%m/%Y}", "temporadas": d["temporada_txt"].value_counts().to_dict(),
            "equipos": int(pd.concat([d.equipo_local_txt, d.equipo_visitante_txt]).nunique()),
            "vacias": n_vacias, "duplicados": int(dup), "errores": errores, "avisos": avisos, "ok": not errores}


if __name__ == "__main__":
    reporte = {"fecha": datetime.now().strftime("%d/%m/%Y %H:%M UTC"), "ligas": {}}
    hay_error = False
    for ruta in sorted(glob.glob("datos/bbdd_*.csv")):
        clave = ruta.split("bbdd_")[1].replace(".csv", "")
        r = validar(ruta)
        reporte["ligas"][clave] = r
        hay_error |= not r["ok"]
        estado = "ERROR" if not r["ok"] else ("AVISO" if r["avisos"] else "OK")
        print(f"[{estado}] {clave}: {r['partidos']} partidos, {r.get('equipos', '?')} equipos, ultimo {r.get('ultimo', '?')}, "
              f"{r['vacias']} celdas vacias")
        for e in r["errores"]:
            print("   ERROR:", e)
        for a in r["avisos"]:
            print("   aviso:", a)
    json.dump(reporte, open("datos/validacion.json", "w"), ensure_ascii=False, indent=1)
    if hay_error:
        print("\nValidacion FALLIDA: no se publican los datos.")
        sys.exit(1)
    print("\nValidacion OK")

"""Corrida de prueba temporal (no va al PR): fotmob.py real + resumen de cobertura."""
import pandas as pd
import fotmob
fotmob.main(list(fotmob.LIGAS))
for l in fotmob.LIGAS:
    b = pd.read_csv(f"datos/bbdd_{l}.csv")
    print(l, "columnas", len(b.columns), "con xg", int(b.xg_local_val.notna().sum()), "de", len(b),
          b.groupby("temporada_txt").xg_local_val.apply(lambda s: int(s.notna().sum())).to_dict())
b = pd.read_csv("datos/bbdd_champions.csv")
print(b.tail(6).iloc[:, [2, 5, 6, 7, 8, 28, 29]].to_string())

"""Diagnóstico temporal (no va al PR): calendario real de FotMob en Champions y cómo se emparejan los nombres."""
import json
import traceback
try:
    import pandas as pd
    import fotmob
    fm = fotmob.calendario(42)
    fm.to_csv("sondeo/fm_champions.csv", index=False)
    b = pd.read_csv("datos/bbdd_champions.csv")
    mapa = fotmob.emparejar_nombres(fm, b)
    json.dump(mapa, open("sondeo/mapa_champions.json", "w"), indent=1, ensure_ascii=False)
except Exception:
    open("sondeo/error.txt", "w").write(traceback.format_exc())

import espn
import generar_bbdd as g


def test_descanso_mayor_al_final_queda_vacio():
    """Un descanso imposible de la fuente (ej. Escocia-Polonia 05/09/2024 en ESPN) no frena la validacion:
    los goles al descanso de ese partido quedan vacios y el resto sigue igual."""
    c = espn.csv_a_crudo("datos/bbdd_mls.csv").head(5).copy()
    c.loc[0, "HTAG"] = c.loc[0, "FTAG"] + 2
    g.EQUIPOS = {}
    o = g.transformar(c)
    assert o.loc[0, ["goles_local_primer_tiempo_val", "goles_visitante_primer_tiempo_val"]].isna().all()
    assert o.loc[0, "goles_visitante_val"] == c.loc[0, "FTAG"]
    assert o.loc[1:, "goles_local_primer_tiempo_val"].notna().all()

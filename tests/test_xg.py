import pandas as pd

import kuota
import understat


def _understat_falso(bbdd: pd.DataFrame) -> pd.DataFrame:
    """La BBDD real con nombres al estilo Understat y la mitad de las fechas corridas un día (Understat usa otra zona horaria)."""
    nombre = lambda e: {"Celta de Vigo": "Celta Vigo", "Alaves": "Alavés"}.get(e, e + " CF")
    f = pd.to_datetime(bbdd.fecha_dt, dayfirst=True) + pd.to_timedelta(bbdd.index % 2, unit="D")
    return pd.DataFrame({"temporada_txt": bbdd.temporada_txt, "fecha": f,
                         "us_local": bbdd.equipo_local_txt.map(nombre), "us_visitante": bbdd.equipo_visitante_txt.map(nombre),
                         "xg_local_val": 1.5, "xg_visitante_val": 0.5})


def test_empareja_todos_los_nombres_por_calendario():
    bbdd = pd.read_csv("datos/bbdd_laliga.csv")
    us = _understat_falso(bbdd)
    mapa = understat.emparejar_nombres(us, bbdd)
    assert mapa["Celta Vigo"] == "Celta de Vigo" and mapa["Alavés"] == "Alaves" and mapa["Real Madrid CF"] == "Real Madrid"
    assert all(u.removesuffix(" CF") == e for u, e in mapa.items() if u.endswith(" CF"))
    assert len(mapa) == len(set(bbdd.equipo_local_txt) | set(bbdd.equipo_visitante_txt))


def test_construir_une_cada_partido_de_la_bbdd():
    bbdd = pd.read_csv("datos/bbdd_laliga.csv")
    xg = understat.construir("laliga", us=_understat_falso(bbdd))
    assert len(xg) == len(bbdd) and list(xg.columns) == understat.COLUMNAS


def test_xg_reciente_local_en_casa_y_visitante_fuera(tmp_path):
    filas = [  # (fecha, local, visitante, xg local, xg visitante)
        ("01/11/2026", "Racing Santander", "Real Madrid", 0.97, 3.36),
        ("25/10/2026", "Barcelona", "Real Madrid", 2.00, 1.00),
        ("18/10/2026", "Real Madrid", "Getafe", 2.50, 0.30),
        ("11/10/2026", "Real Madrid", "Sevilla", 1.50, 0.70),
        ("04/10/2026", "Real Madrid", "Elche", 3.10, 0.20),
    ]
    pd.DataFrame(filas, columns=understat.COLUMNAS[1:]).assign(temporada_txt="2026-27").to_csv(tmp_path / "xg_laliga.csv", index=False)
    xg = kuota.xg_reciente("laliga", "Real Madrid", "Real Madrid", carpeta=str(tmp_path))
    assert xg["local"]["favor"]["n"] == 3 and round(xg["local"]["favor"]["media"], 2) == 2.37
    assert round(xg["local"]["contra"]["media"], 2) == 0.40
    v = xg["visitante"]
    assert v["favor"]["n"] == 2 and round(v["favor"]["media"], 3) == 2.18 and v["favor"]["cv"] is None   # < 3 partidos: sin CV
    assert round(v["contra"]["media"], 3) == 1.485


def test_sin_xg_en_ligas_sin_understat(tmp_path):
    assert kuota.xg_reciente("ligamx", "America", "Toluca", carpeta=str(tmp_path)) is None


def test_compacto_trae_xg_solo_en_goles(tmp_path, monkeypatch):
    df = kuota.cargar("laliga")
    pd.DataFrame([("2026-27", "01/11/2026", "Racing Santander", "Real Madrid", 0.97, 3.36)], columns=understat.COLUMNAS).to_csv(
        tmp_path / "xg_laliga.csv", index=False)
    monkeypatch.setattr(kuota, "CARPETA_DATOS", str(tmp_path))
    goles = kuota.vista_partido(df, "laliga", "Racing Santander", "Real Madrid", "goles", modo="compacto")
    assert goles["xg"]["local"]["favor"]["media"] == 0.97 and goles["xg"]["visitante"]["favor"]["media"] == 3.36
    assert kuota.vista_partido(df, "laliga", "Racing Santander", "Real Madrid", "corners", modo="compacto")["xg"] is None

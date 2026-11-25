import shutil

import openpyxl
import pandas as pd

import fotmob
import generar_bbdd
import kuota
import validar_bbdd

XG6 = fotmob.COLUMNAS[:6]   # temporada, fecha, local, visitante, xg local, xg visitante


def _fotmob_falso(bbdd: pd.DataFrame) -> pd.DataFrame:
    """La BBDD real con nombres al estilo FotMob y la mitad de las fechas corridas un día (FotMob da la fecha en UTC)."""
    nombre = lambda e: {"Celta de Vigo": "Celta Vigo", "Atletico Madrid": "Atlético Madrid"}.get(e, e + " FC")
    f = pd.to_datetime(bbdd.fecha_dt, dayfirst=True) + pd.to_timedelta(bbdd.index % 2, unit="D")
    return pd.DataFrame({"fotmob_id_txt": [str(1000 + i) for i in bbdd.index], "fecha": f,
                         "fm_local": bbdd.equipo_local_txt.map(nombre), "fm_visitante": bbdd.equipo_visitante_txt.map(nombre)})


def _detalle(local="Getafe", xg=(0.5, 4.14)):
    """Detalle de partido con la misma forma que devuelve FotMob (api/data/matchDetails)."""
    return {"general": {"homeTeam": {"name": local, "id": 1}},
            "content": {"stats": {"Periods": {"All": {"stats": [
                {"title": "Top stats", "stats": [{"key": "ball_possession", "rawStats": [{"value": 55}, {"value": 45}]},
                                                 {"key": "expected_goals", "rawStats": [{"value": xg[0]}, {"value": xg[1]}]}]}]}}}}}


def test_empareja_todos_los_nombres_por_calendario():
    bbdd = pd.read_csv("datos/bbdd_laliga.csv")
    mapa = fotmob.emparejar_nombres(_fotmob_falso(bbdd), bbdd)
    assert mapa["Celta Vigo"] == "Celta de Vigo" and mapa["Atlético Madrid"] == "Atletico Madrid" and mapa["Real Madrid FC"] == "Real Madrid"
    assert all(f.removesuffix(" FC") == e for f, e in mapa.items() if f.endswith(" FC"))
    assert len(mapa) == len(set(bbdd.equipo_local_txt) | set(bbdd.equipo_visitante_txt))


def test_champions_real_empareja_por_rivales_aunque_haya_muchos_partidos_el_mismo_dia():
    """Calendario real de FotMob (25/11/2026). Con votos de calendario solos, los equipos nuevos de 2026-27 (5 partidos)
    se cruzaban entre sí (Aston Villa -> Real Betis) porque 18 equipos juegan el mismo martes y miércoles."""
    fm = pd.read_csv("tests/datos/fotmob_champions_calendario.csv", dtype={"fotmob_id_txt": str}, parse_dates=["fecha"])
    bbdd = pd.read_csv("datos/bbdd_champions.csv")
    bbdd = bbdd[pd.to_datetime(bbdd.fecha_dt, dayfirst=True) <= "2026-11-24"]
    mapa = fotmob.emparejar_nombres(fm, bbdd)
    for f, e in {"Aston Villa": "Aston Villa", "Real Betis": "Real Betis", "Inter": "Internazionale", "Roma": "AS Roma",
                 "Viking": "Viking FK", "Feyenoord": "Feyenoord Rotterdam", "RB Leipzig": "RB Leipzig",
                 "Shakhtar Donetsk": "Shakhtar Donetsk", "Sabah FK": "Sabah FK", "Bayern München": "Bayern Munich"}.items():
        assert mapa[f] == e
    assert len(fotmob.unir(fm, bbdd, mapa)) == len(bbdd)


def test_lee_el_xg_del_detalle_de_fotmob():
    assert fotmob.leer_xg(_detalle()) == (0.5, 4.14)
    assert fotmob.leer_xg(_detalle(), local="Getafe") == (0.5, 4.14)
    assert fotmob.leer_xg(_detalle(), local="Atlético Madrid") is None        # local distinto: mejor vacío que al revés
    assert fotmob.leer_xg({"general": {}, "content": {"stats": None}}) is None  # partido sin estadísticas
    assert fotmob.leer_xg(_detalle(xg=(None, 1.2))) is None


def test_construir_une_cada_partido_y_usa_la_cache(tmp_path):
    shutil.copy("datos/bbdd_laliga.csv", tmp_path)
    bbdd = pd.read_csv("datos/bbdd_laliga.csv")
    fm = _fotmob_falso(bbdd)
    pedidos = []
    obtener = lambda mid, local: pedidos.append(mid) or (1.5, 0.5)
    xg = fotmob.construir("laliga", carpeta=str(tmp_path), fm=fm, obtener=obtener)
    assert len(xg) == len(bbdd) == len(pedidos) and list(xg.columns) == fotmob.COLUMNAS
    assert (xg.merge(bbdd, on=["fecha_dt", "equipo_local_txt", "equipo_visitante_txt"]).shape[0]) == len(bbdd)
    xg.iloc[:-3].to_csv(tmp_path / "xg_laliga.csv", index=False)               # caché sin los 3 últimos
    pedidos.clear()
    assert len(fotmob.construir("laliga", carpeta=str(tmp_path), fm=fm, obtener=obtener)) == len(bbdd)
    assert len(pedidos) == 3                                                    # solo pide lo que falta


def test_sin_tiempo_deja_lo_pendiente_para_la_siguiente_corrida(tmp_path):
    shutil.copy("datos/bbdd_laliga.csv", tmp_path)
    fm = _fotmob_falso(pd.read_csv("datos/bbdd_laliga.csv"))
    xg = fotmob.construir("laliga", carpeta=str(tmp_path), fm=fm, obtener=lambda m, l: (1.0, 1.0), hasta=0)
    assert len(xg) == 0


def test_bbdd_sin_xg_queda_identica(tmp_path):
    for liga in ("laliga", "champions"):
        shutil.copy(f"datos/bbdd_{liga}.csv", tmp_path)
        generar_bbdd.refrescar(liga, carpeta=str(tmp_path))
        assert open(f"datos/bbdd_{liga}.csv").read() == open(tmp_path / f"bbdd_{liga}.csv").read()


def test_bbdd_con_xg_suma_dos_columnas_sin_tocar_las_demas(tmp_path):
    shutil.copy("datos/bbdd_laliga.csv", tmp_path)
    bbdd = pd.read_csv("datos/bbdd_laliga.csv")
    p = bbdd.iloc[0]
    pd.DataFrame([[p.temporada_txt, p.fecha_dt, p.equipo_local_txt, p.equipo_visitante_txt, 1.234, 0.5, "99"]],
                 columns=fotmob.COLUMNAS).to_csv(tmp_path / "xg_laliga.csv", index=False)
    generar_bbdd.refrescar("laliga", carpeta=str(tmp_path))
    nuevo = pd.read_csv(tmp_path / "bbdd_laliga.csv")
    assert list(nuevo.columns) == generar_bbdd.COLUMNAS + generar_bbdd.XG
    pd.testing.assert_frame_equal(nuevo[generar_bbdd.COLUMNAS], bbdd)
    assert nuevo.xg_local_val.iloc[0] == 1.23 and nuevo.xg_visitante_val.iloc[0] == 0.5
    assert nuevo.xg_local_val.iloc[1:].isna().all()                             # sin xG = celda vacía
    ws = openpyxl.load_workbook(tmp_path / "bbdd_laliga.xlsx")["partidos"]
    assert [c.value for c in ws[1]][-2:] == generar_bbdd.XG and ws["AC2"].value == 1.23 and ws["AC3"].value is None
    assert ws.auto_filter.ref == f"A1:AD{len(bbdd) + 1}"
    # la validación y el modelo leen la BBDD nueva igual que antes
    assert validar_bbdd.validar(str(tmp_path / "bbdd_laliga.csv"))["ok"]
    a = kuota.vista_partido(kuota.cargar("laliga"), "laliga", "Racing Santander", "Real Madrid", "goles", modo="compacto")
    b = kuota.vista_partido(kuota.cargar("laliga", carpeta=str(tmp_path)), "laliga", "Racing Santander", "Real Madrid", "goles", modo="compacto")
    a.pop("xg"), b.pop("xg")
    assert a == b


def test_xg_reciente_local_en_casa_y_visitante_fuera(tmp_path):
    filas = [  # (fecha, local, visitante, xg local, xg visitante)
        ("01/11/2026", "Racing Santander", "Real Madrid", 0.97, 3.36),
        ("25/10/2026", "Barcelona", "Real Madrid", 2.00, 1.00),
        ("18/10/2026", "Real Madrid", "Getafe", 2.50, 0.30),
        ("11/10/2026", "Real Madrid", "Sevilla", 1.50, 0.70),
        ("04/10/2026", "Real Madrid", "Elche", 3.10, 0.20),
    ]
    pd.DataFrame(filas, columns=XG6[1:]).assign(temporada_txt="2026-27").to_csv(tmp_path / "xg_laliga.csv", index=False)
    xg = kuota.xg_reciente("laliga", "Real Madrid", "Real Madrid", carpeta=str(tmp_path))
    assert xg["fuente"] == "FotMob"
    assert xg["local"]["favor"]["n"] == 3 and round(xg["local"]["favor"]["media"], 2) == 2.37
    assert round(xg["local"]["contra"]["media"], 2) == 0.40
    v = xg["visitante"]
    assert v["favor"]["n"] == 2 and round(v["favor"]["media"], 3) == 2.18 and v["favor"]["cv"] is None   # < 3 partidos: sin CV
    assert round(v["contra"]["media"], 3) == 1.485


def test_sin_xg_si_la_liga_no_tiene_csv(tmp_path):
    assert kuota.xg_reciente("ligamx", "America", "Toluca", carpeta=str(tmp_path)) is None


def test_compacto_trae_xg_solo_en_goles(tmp_path, monkeypatch):
    df = kuota.cargar("laliga")
    pd.DataFrame([("2026-27", "01/11/2026", "Racing Santander", "Real Madrid", 0.97, 3.36, "1")], columns=fotmob.COLUMNAS).to_csv(
        tmp_path / "xg_laliga.csv", index=False)
    monkeypatch.setattr(kuota, "CARPETA_DATOS", str(tmp_path))
    goles = kuota.vista_partido(df, "laliga", "Racing Santander", "Real Madrid", "goles", modo="compacto")
    assert goles["xg"]["local"]["favor"]["media"] == 0.97 and goles["xg"]["visitante"]["favor"]["media"] == 3.36
    assert kuota.vista_partido(df, "laliga", "Racing Santander", "Real Madrid", "corners", modo="compacto")["xg"] is None

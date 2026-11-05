import kuota


def test_media_y_cv_del_ejemplo():
    f = kuota._media_cv([3, 2, 3, 2, 4], kuota.UMBRAL_CV["goles"][0])
    assert f["media"] == 2.8 and round(f["cv"], 4) == 0.2988 and f["estado"] == "regular"


def test_irregular_arriba_del_cv_tipico_del_mercado():
    lim = kuota.UMBRAL_CV["amarillas"][0]
    assert kuota._media_cv([0, 4, 0, 5, 1], lim)["estado"] == "irregular"
    assert kuota._media_cv([2, 2, 3, 2, 2], lim)["estado"] == "regular"


def test_sin_etiqueta_en_rojas_o_media_cero():
    assert kuota._media_cv([0, 1, 0, 0, 0], kuota.UMBRAL_CV["rojas"][0])["estado"] is None
    assert kuota._media_cv([0, 0, 0], 0.5)["cv"] is None


def test_hay_umbral_para_cada_metrica():
    assert set(kuota.UMBRAL_CV) == set(kuota.NOM)


def test_sin_cv_con_menos_de_3_partidos():
    assert kuota._media_cv([7], 0.47) == {"media": 7.0, "cv": None, "n": 1, "limite": 0.47, "estado": None}
    assert kuota._media_cv([11, 8], 0.33)["cv"] is None
    assert kuota._media_cv([11, 8, 9], 0.33)["estado"] is not None

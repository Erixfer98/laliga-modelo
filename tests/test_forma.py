import kuota


def test_media_y_cv_del_ejemplo():
    f = kuota._media_cv([3, 2, 3, 2, 4])
    assert f["media"] == 2.8 and round(f["cv"], 4) == 0.2988 and f["estado"] == "regular"


def test_irregular_arriba_de_0_5_y_sin_cv_si_la_media_es_cero():
    assert kuota._media_cv([0, 4, 0, 5, 1])["estado"] == "irregular"
    assert kuota._media_cv([0, 0, 0])["cv"] is None

"""Lineas por defecto de la tabla: 5 por debajo de λ y 3 por encima."""
import kuota as ku


def test_lineas_por_defecto_5_abajo_3_arriba():
    for lam, esperado in ((26.96, [22.5, 23.5, 24.5, 25.5, 26.5, 27.5, 28.5, 29.5]),
                          (10.1, [5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5, 12.5]),
                          (2.8, [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]),
                          (0.2, [0.5, 1.5, 2.5])):
        cfg = ku.cfg_defecto(lam, 0.0, "tiros", "A", "B")["Total"]
        assert [float(x) for x in ku.lineas(*cfg)] == esperado


def test_cfg_simetrico_sigue_valiendo():
    assert [float(x) for x in ku.lineas(9.5, 2)] == [7.5, 8.5, 9.5, 10.5, 11.5]

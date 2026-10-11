"""Smoke tests de pantallas reales sin credenciales ni efectos externos."""
from unittest.mock import patch
from pathlib import Path

from streamlit.testing.v1 import AppTest

import kuota
from test_probabilidades import leg


def run_app(page, legs):
    at=AppTest.from_file(Path(__file__).resolve().parents[1] / 'app.py',default_timeout=30)
    at.secrets['usuarios']={}
    at.secrets['admins']=''
    at.session_state['pagina']=page
    at.session_state['parlay']=legs
    # Ninguna llamada de red debe ser necesaria para estas pantallas.
    with patch('requests.get', side_effect=AssertionError('red no autorizada en pruebas')), \
         patch('requests.put', side_effect=AssertionError('escritura externa en pruebas')), \
         patch('requests.post', side_effect=AssertionError('red no autorizada en pruebas')):
        at.run()
    assert not at.exception, [x.message for x in at.exception]
    return at


def test_streamlit_inicio_boleto_no_disponible():
    a=leg(); a.update(metrica='Goles',mercado='Gana Real Madrid',cal='Buena',cls='bue')
    at=run_app('Inicio',[a,a])
    assert any('No disponible' in x.value for x in at.markdown)


def test_streamlit_armar_kelly_bloqueado():
    a=leg();a.update(metrica='Goles',mercado='Gana Real Madrid',cal='Buena',cls='bue')
    at=run_app('Armar',[a,a])
    assert any('duplicadas' in x.value for x in at.warning)


def test_streamlit_analizar_cero_y_push():
    at=AppTest.from_file(Path(__file__).resolve().parents[1] / 'app.py',default_timeout=30)
    at.secrets['usuarios']={};at.secrets['admins']=''
    at.session_state['pagina']='Analizar'
    at.session_state['met']='rojas'
    at.session_state['partido_liga']={'laliga':{'local':'Barcelona','visitante':'Real Madrid'}}
    at.run()
    assert not at.exception, [x.message for x in at.exception]

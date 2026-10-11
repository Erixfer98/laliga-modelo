"""Equivalencia entre recorrido de referencia sin caché y API optimizada."""
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import shutil
import numpy as np
import pytest
from fastapi.testclient import TestClient
import api
import kuota
import modelo
from cache_analisis import CacheAnalisis

client = TestClient(api.app)


def comparar(a, b, ruta=""):
    if isinstance(a, dict):
        assert set(a) == set(b), ruta
        for k in a: comparar(a[k], b[k], ruta+"/"+k)
    elif isinstance(a, list):
        assert len(a) == len(b), ruta
        for i,(x,y) in enumerate(zip(a,b)): comparar(x,y,ruta+f"/{i}")
    elif isinstance(a, float):
        assert b == pytest.approx(a, rel=1e-13, abs=1e-14), ruta
    else: assert a == b, ruta


@pytest.mark.parametrize("liga,local,visitante", [
    ("laliga", "Real Madrid", "Barcelona"), ("premier", "Arsenal", "Chelsea")])
@pytest.mark.parametrize("met", list(kuota.NOM))
def test_equivalencia_todas_metricas_mercados_lineas(liga, local, visitante, met):
    df=kuota.cargar(liga); inc=kuota.incertidumbre(df,met)
    for cfg in (None,{"Total":[2.,1],local:[1.5,0],visitante:[0.,1]}):
        for filtro in ("Todos","Como jugarán"):
            referencia=kuota.a_json(kuota.vista_partido(df,liga,local,visitante,met,inc,cfg,8,filtro))
            params={"local":local,"visitante":visitante,"met":met,"n":8,"filtro":filtro}
            if cfg:params["cfg"]=json.dumps(cfg)
            respuesta=client.get(f"/liga/{liga}/partido",params=params)
            assert respuesta.status_code==200,respuesta.text
            obtenido=respuesta.json();version=obtenido.pop("data_version")
            comparar(referencia,obtenido)
            resumen=client.get(f"/liga/{liga}/partido",params={**params,"modo":"resumen"}).json()
            comparar(referencia["mercados"],resumen["mercados"])
            preparada_ref=kuota.preparar_partido(df,local,visitante,met,inc,cfg,8,filtro)
            for mk in referencia["mercados"]:
                detalle=client.get(f"/liga/{liga}/partido",params={**params,"modo":"detalle","pata":mk["mercado"],"data_version":version}).json()
                assert detalle.pop("data_version")==version
                comparar(mk,{k:detalle[k] for k in mk})
                # El detalle de cualquier selección usa el mismo generador de referencia.
                esperado=kuota.a_json(kuota.vista_partido(df,liga,local,visitante,met,inc,cfg,8,filtro,mk["mercado"],_preparado=preparada_ref))["pata"]
                comparar(esperado,detalle)


def test_reutilizacion_distribuciones_y_reglas(monkeypatch):
    api._modelos.limpiar();api._vistas.limpiar();api._mercados.limpiar()
    llamadas=[]; reglas=[]
    original=modelo.analizar; mercado=kuota.pr.prob_evento
    monkeypatch.setattr(modelo,"analizar",lambda *a,**kw:(llamadas.append(1),original(*a,**kw))[1])
    monkeypatch.setattr(kuota.pr,"prob_evento",lambda *a,**kw:(reglas.append(1),mercado(*a,**kw))[1])
    params={"local":"Real Madrid","visitante":"Barcelona","modo":"resumen"}
    assert client.get('/liga/laliga/partido',params=params).status_code==200
    cantidad=len(reglas)
    for extra in ({"grupo":"Total"},{"pata":"Empate"},{"n":10},{"modo":"detalle","pata":"Empate"}):
        assert client.get('/liga/laliga/partido',params={**params,**extra}).status_code==200
    assert len(llamadas)==1
    assert len(reglas)==cantidad
    cfg={"Total":[20.5,0],"Real Madrid":[1.5,1],"Barcelona":[1.5,1]}
    assert client.get('/liga/laliga/partido',params={**params,"cfg":json.dumps(cfg)}).status_code==200
    assert len(llamadas)==1
    assert len(reglas)>cantidad


def test_invalidacion_csv_y_version_detalle(tmp_path,monkeypatch):
    shutil.copy('datos/bbdd_laliga.csv',tmp_path/'bbdd_laliga.csv')
    monkeypatch.setattr(kuota,'CARPETA_DATOS',str(tmp_path));api._cache.clear()
    params={"local":"Real Madrid","visitante":"Barcelona","modo":"resumen"}
    original=client.get('/liga/laliga/partido',params=params).json()
    ruta=tmp_path/'bbdd_laliga.csv'
    import pandas as pd
    df=pd.read_csv(ruta);df.loc[df.index[-1],modelo.METRICAS['goles'][0]]+=1;df.to_csv(ruta,index=False)
    nuevo=client.get('/liga/laliga/partido',params=params).json()
    assert nuevo['data_version']!=original['data_version']
    referencia=kuota.a_json(kuota.vista_partido(kuota.cargar('laliga', carpeta=str(tmp_path)), 'laliga', params['local'], params['visitante'], 'goles', modo='resumen'))
    comparar(referencia['mercados'],nuevo['mercados'])
    assert nuevo['lambda_local']!=original['lambda_local'] or nuevo['lambda_visitante']!=original['lambda_visitante']
    assert client.get('/liga/laliga/partido',params={**params,'modo':'detalle','data_version':original['data_version']}).status_code==409
    api._cache.clear()


def test_cache_limites_concurrencia_y_errores():
    cache=CacheAnalisis(entradas=2,bytes_max=4096);barrera=Barrier(8);llamadas=[]
    def calcular():llamadas.append(1);return np.ones(64)
    def pedir(_):barrera.wait();return cache.obtener('a',calcular)
    with ThreadPoolExecutor(8) as pool:resultados=list(pool.map(pedir,range(8)))
    assert len(llamadas)==1
    assert all(x is resultados[0] for x in resultados)
    for key in ('b','c'):cache.obtener(key,calcular)
    assert len(cache._valores)==2 and cache.bytes<=4096
    cache.obtener('grande',lambda:np.ones(8192));assert 'grande' not in cache._valores
    with pytest.raises(ValueError):cache.obtener('error',lambda:(_ for _ in ()).throw(ValueError()))
    assert 'error' not in cache._valores


def test_version_parametros_y_aislamiento_concurrente(monkeypatch):
    api._modelos.limpiar();api._vistas.limpiar();api._mercados.limpiar()
    llamadas=[];original=modelo.analizar
    monkeypatch.setattr(modelo,'analizar',lambda *a,**kw:(llamadas.append((a[1],a[2],a[3])),original(*a,**kw))[1])
    params={'local':'Real Madrid','visitante':'Barcelona','modo':'resumen'}
    with ThreadPoolExecutor(6) as pool:
        resultados=list(pool.map(lambda _:client.get('/liga/laliga/partido',params=params).json(),range(6)))
    assert len(llamadas)==1
    assert all(x==resultados[0] for x in resultados)
    viejo=resultados[0]['data_version']
    monkeypatch.setattr(modelo,'RHO',-.04)
    nuevo=client.get('/liga/laliga/partido',params=params).json()
    assert nuevo['data_version']!=viejo and len(llamadas)==2
    assert nuevo['mercados'][1]['prob']!=resultados[0]['mercados'][1]['prob']
    assert client.get('/liga/laliga/partido',params={**params,'modo':'detalle','data_version':viejo}).status_code==409
    inverso=client.get('/liga/laliga/partido',params={**params,'local':'Barcelona','visitante':'Real Madrid'}).json()
    assert inverso['local']=='Barcelona' and inverso['visitante']=='Real Madrid'
    assert len(llamadas)==3


def test_verificacion_antes_del_boleto_no_recalcula(monkeypatch):
    params={'local':'Real Madrid','visitante':'Barcelona','modo':'version'}
    def prohibido(*args,**kwargs):raise AssertionError('La verificación no calcula modelos')
    monkeypatch.setattr(modelo,'analizar',prohibido)
    response=client.get('/liga/laliga/partido',params=params)
    assert response.status_code==200 and set(response.json())=={'data_version'}
    version=response.json()['data_version']
    assert client.get('/liga/laliga/partido',params={**params,'data_version':version}).status_code==200
    assert client.get('/liga/laliga/partido',params={**params,'data_version':'obsoleta'}).status_code==409

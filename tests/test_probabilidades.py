"""Regresiones numéricas de la auditoría y propiedades del motor compartido."""
import json
import math
from functools import lru_cache

import numpy as np
import pytest
from scipy.stats import poisson
from fastapi.testclient import TestClient

import modelo as mo
import probabilidades as pr
import kuota as ku
from api import app


@lru_cache(None)
def analisis(liga, local, visitante, met):
    df = ku.cargar(liga)
    return ku.analizar_partido(df, local, visitante, met, ku.incertidumbre(df, met))


def leg(liga="laliga", local="Real Madrid", visitante="Barcelona", met="goles", regla=None, cuota=2.5):
    return {"partido": f"{local} vs {visitante}", "cuota": cuota,
            "prob": .999, "lo": .999, "hi": .999,  # no se deben confiar
            "seleccion": {"liga": liga, "local": local, "visitante": visitante, "metrica": met,
                          "regla": regla or {"tipo": "resultado", "lado": "local"}, "version": pr.VERSION}}


@pytest.mark.parametrize("ll,lv,dc", [(0,0,True),(0,1e-15,True),(1e-10,3,True),(2,2,True),
                                     (19.371780317168874,3.58411836961541,False),
                                     (35.622,10.919,False),(5.019,0,False)])
def test_distribuciones_y_colas(ll,lv,dc):
    m, meta = pr.distribucion(ll,lv,dc)
    assert m.min() >= 0
    assert np.isfinite(m).all()
    assert m.sum() == pytest.approx(1, abs=2e-15)
    assert meta["masa_excluida"] <= pr.TOL_COLA
    assert 1-poisson.cdf(meta["k_max"],ll)*poisson.cdf(meta["k_max"],lv) <= pr.TOL_COLA*1.01


def test_propiedades_aleatorias_y_complementos():
    rng = np.random.default_rng(20261010)
    for _ in range(35):
        ll,lv = rng.uniform(0,50,2)
        m,_ = pr.distribucion(ll,lv)
        for lado in ("local","visitante","total"):
            for ln in (0.,3.,8.5):
                over,push = pr.liquidacion({"tipo":"ou","lado":lado,"linea":ln,"over":True},m.shape[0]-1)
                under,_ = pr.liquidacion({"tipo":"ou","lado":lado,"linea":ln,"over":False},m.shape[0]-1)
                assert np.all(over.astype(int)+under+push == 1)
                assert m[over].sum()+m[under].sum()+m[push].sum() == pytest.approx(1)
                assert 0 <= m[over].sum() <= 1+1e-15


@pytest.mark.parametrize("args", [(25,1,True),(1,25,True),(-1,2,False),(float('nan'),1,False),
                                   (float('inf'),0,False),(1000,2,False)])
def test_distribuciones_invalidas_rechazadas(args):
    with pytest.raises(ValueError):
        pr.distribucion(*args)


@pytest.mark.parametrize("liga,local,vis,met", [
    ("bundesliga","Hoffenheim","Elversberg","goles"),
    ("laliga","Barcelona","Racing Santander","corners"),
    ("bundesliga","Bayern Munich","Elversberg","tiros"),
    ("premier","Coventry","Ipswich","rojas"),
    ("laliga","Barcelona","Real Madrid","rojas")])
def test_regresiones_auditoria(liga,local,vis,met):
    a=analisis(liga,local,vis,met)
    assert a["distribucion"]["masa_excluida"] <= pr.TOL_COLA
    assert a["matriz"].sum() == pytest.approx(1)
    for mk in a["mercados"]:
        assert 0 <= mk["lo"] <= mk["prob"] <= mk["hi"] <= 1+1e-15
        assert mk["prob"]+mk["push"]+mk["loss"] == pytest.approx(1)
        win,push = pr.liquidacion(mk["regla"],a["matriz"].shape[0]-1)
        assert mk["prob"] == pytest.approx(a["matriz"][win].sum(),abs=1e-15)
        assert mk["push"] == pytest.approx(a["matriz"][push].sum(),abs=1e-15)
        g=ku.grafico_modelo(a["matriz"],mk,met)
        if g["tipo"] == "distribucion":
            # Gráfico puede recortar la cola visual, pero no renormaliza las barras.
            assert sum(x["p"] for x in g["valores"] if x["gana"]) <= mk["prob"]+1e-14
    if local == "Barcelona" and met == "rojas":
        assert a["lambda_local"] == 0
        assert a["rango"]["local"][1] > 0
    if met == "tiros":
        assert a["distribucion"]["k_max"] > 35
    if met == "corners":
        mk=next(x for x in a["mercados"] if x["mercado"]=="Barcelona Over 18.5")
        assert mk["prob"] == pytest.approx(poisson.sf(18,a["lambda_local"]),abs=pr.TOL_COLA)


def test_empate_interior_hoff_en_fixture_numerico():
    ll,lv=3.1555709760340464,3.7572906590287856
    center=pr.distribucion(ll,lv,True)[0]
    corners=[pr.distribucion(a,b,True)[0] for a in (2.482592652304303,3.8285492997637895)
             for b in (0,7.514581318057571)]
    assert np.trace(center)>max(np.trace(c) for c in corners)
    a=analisis("bundesliga","Hoffenheim","Elversberg","goles")
    mk=next(m for m in a["mercados"] if m["mercado"]=="Empate")
    assert mk["lo"] <= mk["prob"] <= mk["hi"]


def test_under_tres_push_historial_ev_kelly():
    df=ku.cargar("laliga")
    cfg={"Total":[3.,0],"Real Madrid":[1.5,0],"Barcelona":[1.5,0]}
    a=ku.analizar_partido(df,"Real Madrid","Barcelona","goles",ku.incertidumbre(df,"goles"),cfg)
    mk=next(m for m in a["mercados"] if m["mercado"]=="Total Under 3.0")
    m=a["matriz"];total=np.add.outer(np.arange(len(m)),np.arange(len(m)))
    assert mk["prob"]==pytest.approx(m[total<3].sum())
    assert mk["push"]==pytest.approx(m[total==3].sum())
    hist=ku.historial(df,"Real Madrid","goles",80)
    assert not ku.cumple(hist,mk,"l")[hist.total==3].any()
    ev=ku.ev_pata(mk,3.)
    assert ev["ev"]==pytest.approx(3*mk["prob"]+mk["push"]-1)
    assert mk["justa"]==mo.cuota_justa(mk["prob"],mk["push"])
    # Analítico con push: f=(b*pw-pl)/(b*(pw+pl)).
    dist={3.:.4,1.:.2,0.:.4}
    assert pr.kelly(dist)==pytest.approx(.25)
    assert ku.kelly(.4,3.,.2)==pytest.approx(.25)
    rb=ku.resumen_boleto([leg(regla=mk["regla"],cuota=3.)])
    assert rb["ev"]==pytest.approx(ev["ev"])
    assert rb["push"]==pytest.approx(mk["push"])


def test_conjunta_exacta_y_no_marginales_cliente():
    a=leg();b=leg(regla={"tipo":"ou","lado":"total","linea":2.5,"over":True},cuota=1.8)
    rb=ku.resumen_boleto([a,b])
    r=ku._modelo_boleto("laliga","Real Madrid","Barcelona","goles",__import__('os').path.getmtime('datos/bbdd_laliga.csv'))
    m=r["matriz"];x,y=np.indices(m.shape)
    expected=m[(x>y)&(x+y>2.5)].sum()
    assert rb["disponible"]
    assert rb["prob"]==pytest.approx(expected)
    assert rb["ev"]==pytest.approx(expected*4.5-1)
    assert abs(rb["prob"]-.999**2)>.1
    assert abs(rb["prob"]-m[x>y].sum()*m[x+y>2.5].sum())>1e-3


@pytest.mark.parametrize("kind", ["duplicado","incompatible","sin_modelo","legacy"])
def test_kelly_inseguro_no_disponible(kind):
    a=leg()
    if kind=="duplicado": b=leg()
    elif kind=="incompatible": b=leg(regla={"tipo":"resultado","lado":"visitante"})
    elif kind=="sin_modelo": b=leg(met="corners",regla={"tipo":"ou","lado":"total","linea":10.5,"over":True})
    else: b={"partido":a["partido"],"prob":.5,"cuota":2.5}
    rb=ku.resumen_boleto([a,b]);stk=ku.stake([a,b],1000)
    if kind == "incompatible":
        assert rb["disponible"] and rb["prob"] == 0 and rb["ev"] == pytest.approx(-1)
        assert rb["estado"] == "incompatible" and rb["kelly"] is None
    else:
        assert not rb["disponible"]
        assert rb["prob"] is rb["ev"] is rb["kelly"] is None
    assert stk["kelly"] is None and not stk["disponible"] and stk["opciones"]==[]
    json.dumps(ku.a_json(rb),allow_nan=False)


def test_probabilidad_cero_sin_infinito():
    assert mo.cuota_justa(0) is None
    rb=ku.resumen_boleto([leg(local="Barcelona",visitante="Real Madrid",met="rojas",
        regla={"tipo":"ou","lado":"local","linea":.5,"over":True})])
    assert rb["prob"]==0 and rb["justa"] is None and rb["ev"]==-1
    json.dumps(ku.a_json({"boleto":rb,"inf":math.inf,"nan":math.nan}),allow_nan=False)


@pytest.mark.parametrize("regla", [{"tipo":"ou","lado":"total","linea":2.25,"over":True},
                                    {"tipo":"handicap"},{"tipo":"btts","si":"no"}])
def test_liquidaciones_no_implementadas(regla):
    with pytest.raises(ValueError): ku.resumen_boleto([leg(regla=regla)])


def test_api_contratos_validacion_y_json():
    client=TestClient(app)
    v=client.get('/liga/laliga/partido',params={"local":"Real Madrid","visitante":"Barcelona"})
    assert v.status_code==200
    data=v.json();json.dumps(data,allow_nan=False)
    assert data["sensibilidad"]["cobertura_validada"] is False
    for patas in ([leg()], [leg(),leg()], [leg(),leg(met='corners')]):
        r=client.post('/boleto',json={"patas":patas,"banca":1000})
        assert r.status_code==200
        json.dumps(r.json(),allow_nan=False)
    for body in ({"patas":[leg()],"banca":0},{"patas":"wrong"},
                 {"patas":[leg(regla={"tipo":"handicap"})]}, {"patas":[leg(cuota="nan")]}):
        assert client.post('/boleto',json=body).status_code==422
    assert client.get('/liga/laliga/partido',params={"local":"Real Madrid","visitante":"Barcelona","cfg":"[1]"}).status_code==422


def test_pushes_en_combinada_dependiente_se_liquidan_por_celda():
    a=leg(regla={"tipo":"ou","lado":"local","linea":1.,"over":True},cuota=3.)
    b=leg(regla={"tipo":"ou","lado":"total","linea":3.,"over":False},cuota=1.8)
    rb=ku.resumen_boleto([a,b])
    m=analisis('laliga','Real Madrid','Barcelona','goles')['matriz']
    x,y=np.indices(m.shape)
    payoff=np.where(x>1,3.,np.where(x==1,1.,0.))*np.where(x+y<3,1.8,np.where(x+y==3,1.,0.))
    assert rb['ev']==pytest.approx((m*(payoff-1)).sum())
    assert rb['prob']==pytest.approx(m[(x>1)&(x+y<3)].sum())
    assert rb['push']==pytest.approx(m[payoff==1].sum())
    assert rb['justa'] is None
    assert rb['ev_lo'] <= rb['ev'] <= rb['ev_hi']
    assert rb['kelly'] >= 0


def test_independencia_solo_entre_partidos_distintos():
    a=leg();b=leg(liga='premier',local='Arsenal',visitante='Chelsea')
    sa=ku.resumen_boleto([a]);sb=ku.resumen_boleto([b]);rb=ku.resumen_boleto([a,b])
    assert rb['prob']==pytest.approx(sa['prob']*sb['prob'])
    assert rb['ev']==pytest.approx(rb['prob']*rb['cuota']-1)
    assert any('independencia' in a for a in rb['advertencias'])


def test_duplicado_canonico_entero_vs_float():
    a=leg(regla={"tipo":"ou","lado":"total","linea":3,"over":True})
    b=leg(regla={"over":True,"linea":3.0,"lado":"total","tipo":"ou"})
    assert ku.resumen_boleto([a,b])['estado']=='duplicado'


def test_liga_sin_eventos_cero_finito():
    df=ku.cargar('laliga').head(20).copy()
    cl,cv,_=mo.METRICAS['rojas']
    df[cl]=0;df[cv]=0
    f=mo.fuerzas(df,'rojas')
    assert np.isfinite(f.to_numpy()).all()
    assert mo.lambdas(f,f.index[0],f.index[1])==(0.,0.)
    a=mo.analizar(df,f.index[0],f.index[1],'rojas',inc=mo.incertidumbre(df,'rojas'))
    assert a['matriz'][0,0]==1
    json.dumps(ku.a_json(a),allow_nan=False)


def test_backtest_smoke_motor_compartido(tmp_path):
    import backtest
    # Sin descarga y sin generar reportes reales: tres fechas y métricas cero/noncero.
    filas=[]
    for day in (1,2,3):
        for local,vis in (('A','B'),('B','A')):
            row={'fecha_dt':f'{day:02d}/01/2026','equipo_local_txt':local,'equipo_visitante_txt':vis,
                 'temporada_txt':'2025-26','jornada_val':day}
            for met,(cl,cv,_) in mo.METRICAS.items():
                row[cl]=row[cv]=0 if met=='rojas' else 1
            filas.append(row)
    import pandas as pd
    path=tmp_path/'bbdd_laliga.csv';pd.DataFrame(filas).to_csv(path,index=False)
    pred=backtest.predecir_liga((str(path),list(mo.METRICAS)))
    assert len(pred)>0
    assert np.isfinite(pred['prob_poisson']).all()
    assert pred['prob_poisson'].between(0,1).all()


@pytest.mark.parametrize('valor',[float('inf'),-1,1.5])
def test_conteos_corruptos_no_producen_probabilidades(valor):
    df=ku.cargar('laliga').head(20).copy()
    cl=mo.METRICAS['rojas'][0]
    df[cl]=df[cl].astype(float)
    df.loc[df.index[0],cl]=valor
    with pytest.raises(ValueError): mo.fuerzas(df,'rojas')


def test_cuota_justa_microscopica_no_infinita():
    assert mo.cuota_justa(1e-320) is None
    json.dumps(ku.a_json({'justa':mo.cuota_justa(1e-320)}),allow_nan=False)

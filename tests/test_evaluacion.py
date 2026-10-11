"""Oráculos y pruebas de integración del evaluador temporal, sin descargas."""
import numpy as np
import pandas as pd
import pytest
from scipy.special import expit

import modelo as mo
import probabilidades as pr
from evaluacion.datos import cargar
from evaluacion.temporal import ejecutar_liga, lambdas_referencia
from evaluacion.mercados import probabilidades, observado
from evaluacion.metricas import puntuar, bootstrap_pareado
from evaluacion.calibradores import fit_platt, fit_isotonica, aplicar, temporal


def dataset(tmp_path, n=14):
    rows=[]
    for i in range(n):
        for h,v in [('A','B'),('B','A')]:
            row={'fecha_dt':(pd.Timestamp('2025-01-01')+pd.Timedelta(days=i)).strftime('%d/%m/%Y'),
                 'temporada_txt':'2025-26','equipo_local_txt':h,'equipo_visitante_txt':v}
            for met,(cl,cv,_) in mo.METRICAS.items():
                row[cl]=1+i%3;row[cv]=i%2
            for side in ('local','visitante'):
                row[f'goles_{side}_val']=row[f'goles_{side}_primer_tiempo_val']+row[f'goles_{side}_segundo_tiempo_val']
                row[f'tiros_{side}_val']=5+row[f'tiros_a_puerta_{side}_val']
            rows.append(row)
    path=tmp_path/'bbdd_prueba.csv';pd.DataFrame(rows).to_csv(path,index=False)
    return path


def test_walk_forward_invariante_a_datos_futuros(tmp_path):
    path=dataset(tmp_path)
    before,counts,_=ejecutar_liga(path,('goles',))
    raw=pd.read_csv(path);date=pd.to_datetime(raw.fecha_dt,dayfirst=True);cut=pd.Timestamp('2025-01-09')
    for cl,cv,_ in mo.METRICAS.values(): raw.loc[date>=cut,[cl,cv]]=7
    for side in ('local','visitante'):
        raw[f'goles_{side}_val']=raw[f'goles_{side}_primer_tiempo_val']+raw[f'goles_{side}_segundo_tiempo_val']
    raw.to_csv(path,index=False)
    after,_,_=ejecutar_liga(path,('goles',))
    pd.testing.assert_frame_equal(before[before.fecha<cut].reset_index(drop=True),after[after.fecha<cut].reset_index(drop=True))
    assert (before.train_max_fecha<before.fecha).all()
    assert (counts.train_max_fecha<counts.fecha).all()


def test_equivalencia_fase1_y_misma_fecha_excluida(tmp_path):
    path=dataset(tmp_path);pred,counts,abst=ejecutar_liga(path,('goles',))
    d=cargar(path);date=d.fecha.max();hist=d[d.fecha<date].copy()
    hist['peso']=np.exp(-mo.XI*(date-hist.fecha).dt.days)
    ll,lv=mo.lambdas(mo.fuerzas(hist,'goles'),'A','B')
    central=mo.analizar(hist,'A','B','goles')
    row=pred[(pred.fecha==date)&(pred.local=='A')&(pred.modelo=='actual')&(pred.kind=='ou')&(pred.lado=='total')&(pred.linea==3.)].iloc[0]
    win,push=pr.liquidacion({'tipo':'ou','lado':'total','linea':3.,'over':True},len(central['matriz'])-1)
    assert row.p2==pytest.approx(central['matriz'][win].sum())
    assert row.p1==pytest.approx(central['matriz'][push].sum())
    count=counts[(counts.fecha==date)&(counts.local=='A')&(counts.modelo=='actual')].iloc[0]
    assert count.lambda_local==ll and count.lambda_visitante==lv
    assert count.n_casa==13  # no incluye el partido A-B del propio día
    assert len(abst)==2


def test_equipos_desconocidos_no_reciben_fallback(tmp_path):
    path=dataset(tmp_path);d=pd.read_csv(path)
    d.loc[d.index[-1],'equipo_local_txt']='nuevo';d.to_csv(path,index=False)
    pred,_,abst=ejecutar_liga(path,('goles',))
    assert 'nuevo' not in set(pred.local)
    assert abst.motivo.str.contains('equipo_sin_historial').any()


@pytest.mark.parametrize('change',['faltante','negativo','duplicado','puerta','tiempos'])
def test_datos_corruptos_rechazados(tmp_path,change):
    path=dataset(tmp_path);d=pd.read_csv(path)
    if change=='faltante': d.loc[0,'goles_local_val']=np.nan
    elif change=='negativo':d.loc[0,'rojas_local_val']=-1
    elif change=='duplicado':d=pd.concat([d,d.iloc[:1]])
    elif change=='puerta':d.loc[0,'tiros_a_puerta_local_val']=100
    else:d.loc[0,'goles_local_segundo_tiempo_val']=100
    d.to_csv(path,index=False)
    with pytest.raises(ValueError): cargar(path)


def test_scores_push_y_cero_estructural():
    d=pd.DataFrame({'p0':[.2,1.],'p1':[.3,0.],'p2':[.5,0.],'y':[1,2]})
    s=puntuar(d)
    assert s.brier.iloc[0]==pytest.approx(.5*(.2**2+.7**2+.5**2))
    assert s.logloss.iloc[0]==pytest.approx(-np.log(.3))
    assert s.cero_observado.iloc[1] and np.isinf(s.logloss.iloc[1])
    assert s.logloss_clip.iloc[1]==pytest.approx(-np.log(1e-15))


def test_mascaras_y_resultado_no_confunden_empate_push():
    m=np.zeros((4,4));m[1,1]=.4;m[3,0]=.3;m[0,2]=.3
    markets=[{'kind':'ou','lado':'total','linea':2.,'regla':{'tipo':'ou','lado':'total','linea':2.,'over':True}},
             {'kind':'1x2','regla':{'tipo':'resultado','lado':'local'}}]
    ps=probabilidades(m,markets)
    assert ps[0]==pytest.approx([0.,.7,.3])
    assert ps[1]==pytest.approx([.3,.4,.3])
    assert observado(markets[0],1,1)==1
    assert observado(markets[1],1,1)==1  # nombres distintos aunque índice coincida


def test_isotonica_oraculo_ponderado_y_empates():
    fit=fit_isotonica(np.array([.1,.2,.2,.9]),np.array([1,0,0,1]),np.array([1.,1.,2.,1.]))
    assert aplicar('isotonica',fit,np.array([.1,.2,.9]))==pytest.approx([.25,.25,1.])
    assert (np.diff(aplicar('isotonica',fit,np.linspace(0,1,100)))>=0).all()


def test_platt_recupera_probabilidades_analiticas():
    p=np.linspace(.05,.95,200);target=expit(.7*np.log(p/(1-p))-.3)
    fit=fit_platt(p,target)
    assert fit['a']==pytest.approx(.7,abs=1e-3)
    assert fit['b']==pytest.approx(-.3,abs=1e-3)


def test_calibradores_no_entrenan_en_mes_evaluado(tmp_path):
    path=dataset(tmp_path,n=65);pred,_,_=ejecutar_liga(path,('goles',))
    a,fits,_=temporal(pred,min_partidos=5,min_clase=1)
    assert fits
    for fit in fits: assert pd.Timestamp(fit['train_max_fecha'])<pd.Period(fit['mes_test']).start_time-pd.Timedelta(days=1)
    changed=pred.copy();changed.loc[changed.fecha>=pd.Timestamp('2025-03-01'),'y']=0
    _,fits2,_=temporal(changed,min_partidos=5,min_clase=1)
    march=[x for x in fits if x['mes_test']=='2025-03']
    assert march==[x for x in fits2 if x['mes_test']=='2025-03']
    assert np.allclose(a.p0+a.p1+a.p2,1.)


def test_bootstrap_pareado_reproducible_y_fixture_no_patas():
    rows=[]
    for i in range(30):
        for model,score in [('actual',.1),('liga',.2),('sin_dc',.1),('movil_10',.3)]:
            for _ in range(3):rows.append({'fixture_id':str(i),'fecha':pd.Timestamp('2025-01-01')+pd.Timedelta(days=i),
                'metrica':'goles','modelo':model,'brier':score})
    d=pd.DataFrame(rows);a=bootstrap_pareado(d,replicas=50);b=bootstrap_pareado(d,replicas=50)
    pd.testing.assert_frame_equal(a,b)
    assert (a.partidos==30).all()
    assert a.loc[a.referencia=='liga','delta_brier'].iloc[0]==pytest.approx(-.1)


def test_cli_integracion_reportes_y_graficas(tmp_path):
    from evaluacion.__main__ import main
    import json
    path=dataset(tmp_path,n=8);out=tmp_path/'informe'
    main(['--datos',str(path),'--salida',str(out),'--procesos','1'])
    manifest=json.loads((out/'manifest.json').read_text())
    assert manifest['filas_comunes']==manifest['filas_mercados']>0
    assert manifest['cuotas_verificadas'] is False and manifest['calibracion_en_produccion'] is False
    assert 'as-of' in (out/'REPORTE.md').read_text()
    for name in ('calibracion.png','comparacion.png','errores_colas.png','estabilidad.png'):
        assert (out/name).read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    table=pd.read_csv(out/'comparacion.csv')
    assert set(table.modelo)=={'actual','sin_dc','liga','movil_10'}
    assert (table.brier>=0).all()


def test_cache_verifica_datos_codigo_y_archivos(tmp_path):
    from evaluacion.__main__ import recuperar, CORE
    from evaluacion.datos import sha256, inventario
    import json
    path=dataset(tmp_path,n=6);p,c,a=ejecutar_liga(path,('goles',));out=tmp_path/'cache';out.mkdir()
    p.to_csv(out/'predicciones.csv.gz',index=False,float_format='%.17g')
    c.to_csv(out/'predicciones_conteos.csv.gz',index=False,float_format='%.17g')
    a.to_csv(out/'abstenciones.csv',index=False)
    inv=[inventario(path,cargar(path))]
    meta={'datos':inv,'codigo_sha256':{k:sha256(k) for k in CORE},
          'artefactos_sha256':{k:sha256(out/k) for k in ['predicciones.csv.gz','predicciones_conteos.csv.gz','abstenciones.csv']}}
    (out/'manifest.json').write_text(json.dumps(meta))
    pp,cc,_=recuperar(out,inv)
    np.testing.assert_array_equal(pp[['p0','p1','p2']],p[['p0','p1','p2']])
    assert len(cc)==len(c)
    with pytest.raises(ValueError,match='datos cambiaron'):
        recuperar(out,[{**inv[0],'sha256':'incorrecto'}])
    (out/'abstenciones.csv').write_text('corrupto')
    with pytest.raises(ValueError,match='hash válido'): recuperar(out,inv)


def test_probabilidad_cola_no_se_pierde_por_complemento():
    # P(Under 0.5) es microscópica y se perdería usando 1-P(Over).
    m,_=pr.distribucion(50.,1.)
    market={'kind':'ou','lado':'local','linea':.5,'regla':{'tipo':'ou','lado':'local','linea':.5,'over':True}}
    p=probabilidades(m,[market])[0]
    assert p[0]>0 and p[0]==pytest.approx(np.exp(-50),rel=1e-12,abs=0.)


def test_bins_exactos_y_probabilidad_cien_no_desaparece():
    from evaluacion.metricas import calibracion
    ps=np.array([.5,.6,.7,.8,.9,1.])
    d=pd.DataFrame({'fixture_id':[str(i) for i in range(6)],'kind':'ou','linea':.5,
                    'modelo':'actual','p0':1-ps,'p1':0.,'p2':ps,'y':2})
    cal=calibracion(d,['modelo']);over=cal[cal.evento=='Over']
    assert over.selecciones.sum()==6
    assert over.loc[over.p_media==.6,'bin'].iloc[0]=='[0.6, 0.7)'
    last=over[over['bin']=='[0.9, 1.0)']
    assert last.selecciones.iloc[0]==2


def test_cli_no_duplica_ligas(tmp_path):
    from evaluacion.__main__ import main
    path=dataset(tmp_path,n=2)
    with pytest.raises(ValueError,match='Ligas duplicadas'):
        main(['--datos',str(path),str(path),'--salida',str(tmp_path/'salida')])

"""Causalidad, oráculos probabilísticos y registro experimental."""
from datetime import datetime,timedelta,timezone
import copy
import json
import hashlib
import sqlite3

import numpy as np
import pandas as pd
import pytest
from scipy.stats import poisson, nbinom

from evaluacion.datos import cargar
from evaluacion.mercados import registro, probabilidades
from experimentos.lambdas import Config, resumen_historial, estimar, rejilla
from experimentos.distribuciones import predecir, score_primario, ajustar_alpha
from experimentos.temporal import seleccionar, dispersion_nb
from experimentos.registro import Registro, validar
import probabilidades as pr


def historial():
    rows=[]
    for i in range(12):
        rows.append({'fecha':pd.Timestamp('2025-01-01')+pd.Timedelta(days=i),
            'equipo_local_txt':'A','equipo_visitante_txt':'B','goles_local_val':0,
            'goles_visitante_val':0})
    return pd.DataFrame(rows)


def test_lambdas_positivas_ceros_y_equipos_nuevos():
    h=historial();summary=resumen_historial(h,pd.Timestamp('2025-02-01'),'goles',.005)
    for conf in rejilla('goles'):
        assert min(estimar(summary,'A','B',conf,(0.,0.)))>0
        assert min(estimar(summary,'nuevo','otro',conf))>0
    assert estimar(summary,'nuevo','otro',Config(3))==pytest.approx(summary[:2])


def test_encogimiento_oraculo_y_historial_futuro_rechazado():
    summary=(2.,1.,{'A':(3.,12.,3.)},{'B':(4.,8.,8.)})
    assert estimar(summary,'A','B',Config(3))==pytest.approx((3.,11/7))
    with pytest.raises(ValueError,match='Historial futuro'):
        resumen_historial(historial(),pd.Timestamp('2025-01-05'),'goles',.005)


def test_probabilidades_poisson_dc_coinciden_fase1():
    for ll,lv,rho in [(1.8,.9,-.05),(2.,1.,0.),(.001,.003,0.)]:
        markets=[m for m in registro('goles',ll,lv) if m['fija']]
        rows,diag=predecir(ll,lv,markets,1,2,rho)
        m,_=pr.distribucion(ll,lv,bool(rho),rho,k=30)
        np.testing.assert_allclose(np.array([[r['p0'],r['p1'],r['p2']] for r in rows]),
                                   probabilidades(m,markets),atol=2e-12,rtol=1e-10)
        assert diag['masa_excluida']<=1e-12
        expected=poisson.logpmf(1,ll)+poisson.logpmf(2,lv)
        assert diag['nll_conjunta']==pytest.approx(-expected)


def test_score_primario_oraculo_y_cola_microscopica():
    ll,lv=1.8,.9;lines=[.5,1.,1.5,2.,2.5]
    markets=[{'kind':'ou','lado':'total','linea':v,'fija':True,'defecto':False} for v in lines]
    rows,_=predecir(ll,lv,markets,1,1,-.05)
    from evaluacion.metricas import puntuar
    expected=puntuar(pd.DataFrame(rows)).brier.mean()
    assert score_primario(np.array([ll]),np.array([lv]),1,1,lines,rho=-.05)[0]==pytest.approx(expected)
    markets=[{'kind':'ou','lado':'local','linea':40.5}]
    rows,_=predecir(4.,2.,markets,1,1)
    assert rows[0]['p2']>0 and rows[0]['p2']==pytest.approx(poisson.sf(40,4),rel=1e-10,abs=0)


def test_nb_oraculo_marginal_total_y_limite_poisson():
    markets=[{'kind':'ou','lado':side,'linea':v} for side in ('total','local','visitante') for v in (.5,2.,3.5)]
    rows,diag=predecir(2.,2.,markets,2,3,alpha=.2)
    # Igual p permite sumar dos NB con r=5: total NB r=10.
    for row in rows:
        dist=nbinom(10 if row['lado']=='total' else 5,1/1.4)
        assert row['p2']==pytest.approx(dist.sf(np.floor(row['linea'])),abs=2e-12)
    assert diag['var_local']==pytest.approx(2.8)
    a,_=predecir(2.,3.,markets,2,3)
    b,_=predecir(2.,3.,markets,2,3,alpha=1e-10)
    assert a==b
    with pytest.raises(ValueError,match='DC no está definido'): predecir(2,2,markets,1,1,-.05,.2)


def bank_sintetico():
    rows=[];configs=rejilla('tiros')
    for i in range(120):
        date=pd.Timestamp('2025-01-01')+pd.Timedelta(days=i)
        for index,c in enumerate(configs):
            rows.append(dict(fixture_id=str(i),fecha=date,liga='prueba',metrica='tiros',candidato=c.id,
                lambda_local=10.,lambda_visitante=10.,real_local=15.,real_visitante=10.,
                brier_interno=.1 if index==0 else .2))
    return pd.DataFrame(rows)


def test_seleccion_anidada_no_usa_mes_externo_y_nb_tampoco():
    bank=bank_sintetico();a,_=seleccionar(bank,min_partidos=10,min_meses=2)
    aa=dispersion_nb(bank,a)
    modified=bank.copy();mask=modified.fecha>=pd.Timestamp('2025-04-01')
    modified.loc[mask,'brier_interno']=100.
    modified.loc[mask,'real_local']=500.
    b,_=seleccionar(modified,min_partidos=10,min_meses=2)
    bb=dispersion_nb(modified,b)
    assert [x for x in aa if x['mes_externo']=='2025-04']==[x for x in bb if x['mes_externo']=='2025-04']
    for fit in aa:
        assert pd.Timestamp(fit['train_max_fecha'])<pd.Timestamp(fit['cutoff_exclusivo'])
    with pytest.raises(ValueError,match='cohortes internas'):
        seleccionar(bank.drop(index=0),min_partidos=10,min_meses=2)


def test_dispersion_nb_no_se_activa_sin_exceso_interno():
    bank=bank_sintetico();bank['real_local']=10.
    a,_=seleccionar(bank,min_partidos=10,min_meses=2)
    assert a and not any(x['nb_habilitada'] for x in a)
    assert all(x['alpha']==0 for x in dispersion_nb(bank,a))


def payload(snapshot):
    now=datetime.now(timezone.utc)
    return {'fixture_id':'official-123','liga':'laliga','kickoff_utc':(now+timedelta(days=1)).isoformat(),
        'generated_at_utc':(now-timedelta(seconds=1)).isoformat(),'modelo_version':'experimental-v1',
        'codigo_commit':'a'*40,'configuracion':{'kappa':3.,'xi':.005,'rho':0.,'alpha':0.},'metrica':'goles','kind':'ou','lado':'total','linea':2.5,
        'lambdas':[1.5,1.],'probabilidades':[.4,0.,.6],'alcance':'regulation','experimental':True,
        'datos':[{'snapshot_sha256':hashlib.sha256(snapshot.read_bytes()).hexdigest(),'source':'fixture-test',
                  'captured_at_utc':(now-timedelta(minutes=2)).isoformat(),
                  'available_at_utc':(now-timedelta(minutes=3)).isoformat(),
                  'as_of_utc':(now-timedelta(minutes=1)).isoformat()}]}


def test_registro_append_only_idempotencia_y_procedencia(tmp_path):
    snapshot=tmp_path/'snapshot.csv';snapshot.write_text('fixture,data\n123,1\n')
    db=Registro(tmp_path/'registro.sqlite');p=payload(snapshot)
    a=db.agregar(p,[snapshot]);assert db.agregar(p,[snapshot])==a and db.verificar()==1
    q=copy.deepcopy(p);q['lambdas']=[2.,1.]
    assert db.agregar(q,[snapshot])!=a and db.verificar()==2
    with sqlite3.connect(db.path) as connection:
        with pytest.raises(sqlite3.IntegrityError,match='inmutable'):
            connection.execute('DELETE FROM predicciones')
    snapshot.write_text('alterado')
    with pytest.raises(ValueError,match='Hashes'): db.agregar(p,[snapshot])


@pytest.mark.parametrize('failure',['future_data','kickoff','naive','prob','commit','push','experimental'])
def test_registro_rechaza_inconsistencias(tmp_path,failure):
    file=tmp_path/'snapshot';file.write_text('test');p=payload(file)
    if failure=='future_data':p['datos'][0]['available_at_utc']=p['kickoff_utc']
    elif failure=='kickoff':p['kickoff_utc']=p['generated_at_utc']
    elif failure=='naive':p['generated_at_utc']='2025-01-01T10:00:00'
    elif failure=='prob':p['probabilidades']=[.5,0.,.6]
    elif failure=='commit':p['codigo_commit']='main'
    elif failure=='push':p['probabilidades']=[.4,.1,.5]
    else:p['experimental']=False
    with pytest.raises(ValueError):validar(p)


def test_banco_causal_e_integracion_con_comparadores(tmp_path):
    from test_evaluacion import dataset
    from evaluacion.temporal import ejecutar_liga
    from experimentos.temporal import banco_liga,evaluar_seleccion
    from evaluacion.comparabilidad import cohorte,MERCADO
    path=dataset(tmp_path,n=65)
    baseline,counts,_=ejecutar_liga(path,('goles',))
    data=cargar(path);bank=banco_liga(data,counts,('goles',))
    selection,_=seleccionar(bank,min_partidos=5,min_meses=1)
    assert selection
    pred,diag=evaluar_seleccion(bank,counts,selection)
    keys=pred[MERCADO].drop_duplicates()
    old=baseline[baseline.maduro&baseline.fija].merge(keys,on=MERCADO,how='inner')
    common,_=cohorte(pd.concat([old,pred],ignore_index=True),
                    modelos=('actual','sin_dc','liga','movil_10','poisson_regularizado','regularizado_sin_dc'))
    assert len(common)==len(old)+len(pred)
    assert np.isfinite(diag.nll_conjunta).all()
    # Alterar resultados futuros no cambia lambdas ni scores de predicciones anteriores.
    date=pd.Timestamp('2025-02-15');changed=data.copy();mask=changed.fecha>=date
    changed.loc[mask,['goles_local_val','goles_visitante_val']]=20
    later=banco_liga(changed,counts,('goles',))
    pd.testing.assert_frame_equal(bank[bank.fecha<date].reset_index(drop=True),later[later.fecha<date].reset_index(drop=True))


def test_holm_oraculo_y_logloss_infinito_no_se_oculta():
    from experimentos.reportes import holm,intervalos
    assert holm([.01,.03,.04])==pytest.approx([.03,.06,.06])
    rows=[]
    for i in range(20):
        for model,bs,ll in [('actual',.2,np.inf),('liga',.3,.5),('movil_10',.3,.5),('poisson_regularizado',.1,.3)]:
            rows.append(dict(fixture_id=str(i),fecha=pd.Timestamp('2025-01-01')+pd.Timedelta(days=i),
                metrica='tiros',kind='ou',lado='local',linea=.5,modelo=model,y=2,brier=bs,logloss=ll))
    result=intervalos(pd.DataFrame(rows),replicas=50)
    actual=result[result.referencia=='actual'].iloc[0]
    assert np.isinf(actual.mejora_logloss)
    assert not actual.logloss_inferencia_finita and pd.isna(actual.logloss_ic95_lo)
    assert actual.mejora_brier==pytest.approx(.1)
    assert actual.ic95_14d_lo==pytest.approx(.1)
    pair=pd.DataFrame(rows);pair=pair[pair.modelo.isin(['actual','poisson_regularizado'])]
    diagnostic=intervalos(pair,replicas=50,referencias=('actual',),familia_primaria=False)
    assert diagnostic.p_holm.isna().all() and not diagnostic.primario.any()
    assert diagnostic.mejora_brier.iloc[0]==pytest.approx(.1)


def test_produccion_no_importa_experimentos():
    import ast
    from pathlib import Path
    for name in ('api.py','app.py','modelo.py','probabilidades.py','kuota.py','backtest.py'):
        for node in ast.walk(ast.parse(Path(name).read_text())):
            if isinstance(node,ast.Import):names=[n.name for n in node.names]
            elif isinstance(node,ast.ImportFrom):names=[node.module or '']
            else:continue
            assert not any(n.startswith('experimentos') for n in names)


def test_registro_normaliza_utc_y_rechaza_insercion_tardia(tmp_path):
    snapshot=tmp_path/'datos';snapshot.write_text('verified-by-hash')
    db=Registro(tmp_path/'registro.sqlite');p=payload(snapshot)
    a=db.agregar(p,[snapshot]);offset=copy.deepcopy(p)
    for key in ('kickoff_utc','generated_at_utc'):
        offset[key]=datetime.fromisoformat(p[key]).astimezone(timezone(timedelta(hours=2))).isoformat()
    for source in offset['datos']:
        for key in ('captured_at_utc','available_at_utc','as_of_utc'):
            source[key]=datetime.fromisoformat(source[key]).astimezone(timezone(timedelta(hours=2))).isoformat()
    assert db.agregar(offset,[snapshot])==a and db.verificar()==1
    late=copy.deepcopy(p)
    for key in ('kickoff_utc','generated_at_utc'):
        late[key]=(datetime.fromisoformat(p[key])-timedelta(days=3)).isoformat()
    for source in late['datos']:
        for key in ('captured_at_utc','available_at_utc','as_of_utc'):
            source[key]=(datetime.fromisoformat(source[key])-timedelta(days=3)).isoformat()
    with pytest.raises(ValueError,match='después del kickoff'):db.agregar(late,[snapshot])
    assert db.verificar()==1


def test_cadena_detecta_alteracion_del_registro(tmp_path):
    snapshot=tmp_path/'datos';snapshot.write_text('test')
    db=Registro(tmp_path/'registro.sqlite');db.agregar(payload(snapshot),[snapshot])
    with sqlite3.connect(db.path) as connection:
        connection.execute('DROP TRIGGER sin_update')
        connection.execute("UPDATE predicciones SET previous_hash='corrupto'")
    with pytest.raises(ValueError,match='alterada'):db.verificar()


def test_cli_piloto_y_cache_rechazan_datos_o_artefactos_alterados(tmp_path):
    from test_evaluacion import dataset
    from evaluacion.temporal import ejecutar_liga
    from evaluacion.datos import inventario,sha256
    from evaluacion.__main__ import CORE
    from experimentos.__main__ import main
    original=dataset(tmp_path,n=8);path=tmp_path/'bbdd_laliga.csv';original.rename(path)
    _,counts,_=ejecutar_liga(path,('goles',))
    cache=tmp_path/'fase2';cache.mkdir();out=tmp_path/'fase3'
    counts.to_csv(cache/'predicciones_conteos.csv.gz',index=False,float_format='%.17g')
    meta={'codigo_sha256':{p:sha256(p) for p in CORE},'datos':[inventario(path,cargar(path))],
          'artefactos_sha256':{'predicciones_conteos.csv.gz':sha256(cache/'predicciones_conteos.csv.gz')}}
    (cache/'manifest.json').write_text(json.dumps(meta))
    args=['--salida',str(out),'--cache-fase2',str(cache)]
    main([*args,'--piloto'])
    pilot=json.loads((out/'piloto.json').read_text())
    assert pilot['filas_banco']>0 and pilot['nb_evaluada'] is False
    changed=copy.deepcopy(pilot);changed['codigo_banco']={}
    (out/'piloto.json').write_text(json.dumps(changed))
    with pytest.raises(ValueError,match='Piloto obsoleto'):main(args)
    (out/'piloto.json').write_text(json.dumps(pilot))
    (cache/'predicciones_conteos.csv.gz').write_text('corrupto')
    with pytest.raises(ValueError,match='Conteos Fase 2 alterados'):main(args)
    path.write_text(path.read_text()+'\n')
    with pytest.raises(ValueError,match='Histórico distinto'):main(args)


@pytest.mark.parametrize('month',['2025-03','2025-04'])
def test_anidacion_perturbacion_desde_embargo_y_prefijo(month):
    bank=bank_sintetico()
    fits,_=seleccionar(bank,min_partidos=10,min_meses=2)
    expected=next(f for f in dispersion_nb(bank,fits) if f['mes_externo']==month)
    cutoff=pd.Period(month,'M').start_time-pd.Timedelta(days=1)
    changed=bank.copy();future=changed.fecha>=cutoff
    # Incluye el día de embargo, mes externo y todos los meses posteriores.
    changed.loc[future,['real_local','real_visitante']]=[500.,0.]
    changed.loc[future,['lambda_local','lambda_visitante']]=[.001,900.]
    changed.loc[future,'brier_interno']=np.arange(future.sum())%26
    perturbed,_=seleccionar(changed,min_partidos=10,min_meses=2)
    actual=next(f for f in dispersion_nb(changed,perturbed) if f['mes_externo']==month)
    assert actual==expected  # candidato, κ/ξ/ventana/ρ, Pearson, gate y α NB.
    # La fila del mes externo solo enumera el corte; sus valores no lo ajustan.
    prefix=bank[(bank.fecha<cutoff)|(bank.fecha==pd.Period(month,'M').start_time)]
    partial,_=seleccionar(prefix,min_partidos=10,min_meses=2)
    assert next(f for f in dispersion_nb(prefix,partial) if f['mes_externo']==month)==expected


def test_registro_recibo_evidencia_archivada_y_reintento_post_kickoff(tmp_path,monkeypatch):
    import experimentos.registro as module
    snapshot=tmp_path/'datos';snapshot.write_bytes(b'original evidence')
    p=payload(snapshot);now=datetime.now(timezone.utc)
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None): return now.astimezone(tz)
    monkeypatch.setattr(module,'datetime',Clock)
    db=Registro(tmp_path/'registro.sqlite');ident=db.agregar(p,[snapshot])
    receipt=db.consultar(ident)
    assert receipt['generated_at_utc']!=receipt['registered_at_utc']
    assert receipt['registered_at_utc']==now.isoformat()
    assert receipt['valida_para_evaluacion_prospectiva'] and receipt['snapshots_verificados']
    assert receipt['disponibilidad_proveedor_certificada'] is False
    now=datetime.fromisoformat(p['kickoff_utc'])
    assert db.agregar(p,[snapshot])==ident  # El reintento no crea evidencia nueva.
    assert db.consultar(ident)==receipt and db.verificar()==1
    q=copy.deepcopy(p);q['lambdas'][0]=2.
    with pytest.raises(ValueError,match='después del kickoff'): db.agregar(q,[snapshot])
    now+=timedelta(seconds=1)
    with pytest.raises(ValueError,match='después del kickoff'): db.agregar(q,[snapshot])
    snapshot.unlink()
    assert db.consultar(ident)==receipt  # La prueba conserva los bytes originales.
    forged=copy.deepcopy(p);forged['registered_at_utc']=p['generated_at_utc']
    with pytest.raises(ValueError,match='campos desconocidos'): validar(forged)


@pytest.mark.parametrize('failure',['missing','tampered'])
def test_registro_no_valida_procedencia_ausente_o_alterada(tmp_path,failure):
    snapshot=tmp_path/'datos';snapshot.write_text('original')
    db=Registro(tmp_path/'registro.sqlite');ident=db.agregar(payload(snapshot),[snapshot])
    with sqlite3.connect(db.path) as connection:
        with pytest.raises(sqlite3.IntegrityError,match='inmutable'):
            connection.execute('UPDATE snapshots SET contenido=?',(b'fake',))
        connection.execute('DROP TRIGGER snapshots_sin_update')
        connection.execute('DROP TRIGGER snapshots_sin_delete')
        if failure=='missing': connection.execute('DELETE FROM snapshots')
        else: connection.execute('UPDATE snapshots SET contenido=?',(b'fake',))
    with pytest.raises(ValueError,match='Procedencia archivada'): db.consultar(ident)
    with pytest.raises(ValueError,match='Procedencia archivada'): db.verificar()


def test_registro_rechazo_tardio_revierte_archivo_e_idempotencia_concurrente(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    snapshot=tmp_path/'datos';snapshot.write_text('original')
    db=Registro(tmp_path/'registro.sqlite');p=payload(snapshot)
    with ThreadPoolExecutor(max_workers=4) as pool:
        identifiers=list(pool.map(lambda _:db.agregar(p,[snapshot]),range(8)))
    assert len(set(identifiers))==1 and db.verificar()==1
    snapshot.write_text('different evidence');late=payload(snapshot)
    for key in ('kickoff_utc','generated_at_utc'):
        late[key]=(datetime.fromisoformat(late[key])-timedelta(days=3)).isoformat()
    for source in late['datos']:
        for key in ('captured_at_utc','available_at_utc','as_of_utc'):
            source[key]=(datetime.fromisoformat(source[key])-timedelta(days=3)).isoformat()
    with pytest.raises(ValueError,match='después del kickoff'): db.agregar(late,[snapshot])
    with sqlite3.connect(db.path) as connection:
        assert connection.execute('SELECT COUNT(*) FROM snapshots').fetchone()[0]==1
    assert db.verificar()==1


def test_pipeline_crudo_hasta_nb_y_predicciones_no_cambia_por_datos_futuros(tmp_path):
    from test_evaluacion import dataset
    from evaluacion.temporal import ejecutar_liga
    from experimentos.temporal import banco_liga,evaluar_seleccion
    path=dataset(tmp_path,n=95);cut=pd.Timestamp('2025-03-15')
    def run():
        _,counts,_=ejecutar_liga(path,('tiros',))
        bank=banco_liga(cargar(path),counts,('tiros',))
        fits,_=seleccionar(bank,min_partidos=10,min_meses=1)
        fits=dispersion_nb(bank,fits)
        pred,diag=evaluar_seleccion(bank,counts,fits,incluir_nb=True)
        return bank,fits,pred,diag
    bank,fits,pred,diag=run()
    raw=pd.read_csv(path);future=pd.to_datetime(raw.fecha_dt,dayfirst=True)>=cut
    raw.loc[future,['tiros_local_val','tiros_visitante_val']]=[1000,500]
    raw.to_csv(path,index=False)
    later,changed,ps,ds=run()
    for before,after in ((bank,later),(pred,ps),(diag,ds)):
        early=before[before.fecha<cut].reset_index(drop=True)
        assert not early.empty
        pd.testing.assert_frame_equal(early,after[after.fecha<cut].reset_index(drop=True))
    month=str(cut.to_period('M'))
    assert [f for f in fits if f['mes_externo']<=month]==[f for f in changed if f['mes_externo']<=month]


def test_hora_de_registro_se_toma_despues_del_lock_y_archivo(tmp_path,monkeypatch):
    import experimentos.registro as module
    snapshot=tmp_path/'datos';snapshot.write_text('original')
    p=payload(snapshot);times=iter([datetime.now(timezone.utc),datetime.fromisoformat(p['kickoff_utc'])])
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None): return next(times).astimezone(tz)
    monkeypatch.setattr(module,'datetime',Clock)
    db=Registro(tmp_path/'registro.sqlite')
    with pytest.raises(ValueError,match='después del kickoff'): db.agregar(p,[snapshot])
    with sqlite3.connect(db.path) as connection:
        assert connection.execute('SELECT COUNT(*) FROM predicciones').fetchone()[0]==0
        assert connection.execute('SELECT COUNT(*) FROM snapshots').fetchone()[0]==0


def test_cli_registro_expone_recibo_con_hora_efectiva(tmp_path,monkeypatch,capsys):
    import sys
    from experimentos.registro import main
    snapshot=tmp_path/'datos';snapshot.write_text('original')
    p=payload(snapshot);entrada=tmp_path/'prediccion.json';entrada.write_text(json.dumps(p))
    monkeypatch.setattr(sys,'argv',['registro','--db',str(tmp_path/'registro.sqlite'),
        '--entrada',str(entrada),'--snapshot',str(snapshot),'--recibo'])
    main();receipt=json.loads(capsys.readouterr().out)
    assert receipt['generated_at_utc']==p['generated_at_utc']
    assert datetime.fromisoformat(receipt['generated_at_utc'])<datetime.fromisoformat(receipt['registered_at_utc'])<datetime.fromisoformat(receipt['kickoff_utc'])
    assert receipt['snapshots_verificados'] is True

"""Fase 3 opt-in: piloto obligatorio, Poisson primero, NB condicionada después."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import platform
import time
import numpy as np
import pandas as pd
import scipy
import matplotlib

from evaluacion.datos import cargar, inventario, sha256
from evaluacion.__main__ import CORE as FASE2_CORE
from evaluacion.comparabilidad import cohorte, validar_temporal
from evaluacion.metricas import puntuar
from .lambdas import rejilla
from .distribuciones import predecir
from evaluacion.mercados import registro
from .temporal import banco_liga, seleccionar, dispersion_nb, evaluar_seleccion
from . import VERSION

BANK_CORE=('experimentos/lambdas.py','experimentos/distribuciones.py','experimentos/temporal.py')


def escribir(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def cargar_counts(cache):
    meta=json.loads((cache/'manifest.json').read_text())
    if any(meta['codigo_sha256'].get(p)!=sha256(p) for p in FASE2_CORE):
        raise ValueError('Motor Fase 2 distinto: regenerar referencias')
    for d in meta['datos']:
        if sha256(d['archivo'])!=d['sha256']: raise ValueError('Histórico distinto al caché Fase 2')
    name='predicciones_conteos.csv.gz'
    if sha256(cache/name)!=meta['artefactos_sha256'][name]: raise ValueError('Conteos Fase 2 alterados')
    counts=pd.read_csv(cache/name,parse_dates=['fecha','train_max_fecha'],float_precision='round_trip')
    validar_temporal(counts);cohorte(counts,keys=['fixture_id','metrica'])
    return counts,meta


def trabajar(args):
    path,counts=args
    return banco_liga(cargar(path),counts)


def fuentes(meta):
    return {d['archivo']:d['sha256'] for d in meta['datos']}


def core():
    return {p:sha256(p) for p in BANK_CORE}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida',default='docs/fase3')
    parser.add_argument('--cache-fase2',default='docs/fase2')
    parser.add_argument('--procesos',type=int,default=2)
    parser.add_argument('--piloto',action='store_true')
    parser.add_argument('--reusar-inferencia',action='store_true',help='Regenerar reportes desde predicciones verificadas')
    parser.add_argument('--etapa',choices=['poisson','nb'],default='poisson')
    args=parser.parse_args(argv)
    if args.procesos<1: parser.error('--procesos debe ser positiva')
    out=Path(args.salida);out.mkdir(parents=True,exist_ok=True)
    counts,meta=cargar_counts(Path(args.cache_fase2))
    started=time.perf_counter()
    if args.piloto:
        entry=next(d for d in meta['datos'] if d['liga']=='laliga')
        sample=banco_liga(cargar(entry['archivo']),counts[counts.liga=='laliga'],('tiros','goles'),60)
        elapsed=time.perf_counter()-started
        representative=sample.drop_duplicates(['fixture_id','metrica'])
        pred_started=time.perf_counter()
        for row in representative.itertuples(index=False):
            markets=[m for m in registro(row.metrica,row.lambda_local,row.lambda_visitante) if m['fija']]
            predecir(row.lambda_local,row.lambda_visitante,markets,row.real_local,row.real_visitante,row.rho)
        prediction_seconds=time.perf_counter()-pred_started
        total=sum(len(rejilla(m))*len(g) for m,g in counts[(counts.modelo=='actual')&counts.maduro].groupby('metrica'))
        # Piloto mide coste, no selecciona modelos ni prueba ventajas estadísticas.
        proof={'tipo':'piloto_rendimiento; sin inferencia predictiva','segundos':elapsed,
               'filas_banco':len(sample),'partidos':int(sample.fixture_id.nunique()),
               'segundos_probabilidades':prediction_seconds,'predicciones_conteo_piloto':len(representative),
               'filas_estimadas_completo':total,'estimacion_segundos_serial':elapsed*total/len(sample),
               'estimacion_probabilidades_poisson_serial':prediction_seconds*len(counts[(counts.modelo=='actual')&counts.maduro])*2/len(representative),
               'codigo_banco':core(),'datos':fuentes(meta),'memoria_banco_muestra_bytes':int(sample.memory_usage(deep=True).sum()),
               'procesos_completo':args.procesos,'nb_evaluada':False}
        escribir(out/'piloto.json',proof);print(json.dumps(proof,ensure_ascii=False),flush=True);return
    protocol_path=out/'protocolo.json'
    if not protocol_path.exists():
        protocol_path.write_text(Path('docs/fase3/protocolo.json').read_text())
    protocol=json.loads(protocol_path.read_text())
    if protocol['codigo_banco']!=core(): raise ValueError('Protocolo distinto al código experimental')
    pilot=json.loads((out/'piloto.json').read_text())
    if pilot['codigo_banco']!=core() or pilot['datos']!=fuentes(meta): raise ValueError('Piloto obsoleto')
    previous=None
    if args.reusar_inferencia:
        previous=json.loads((out/'manifest.json').read_text())
        if fuentes(previous)!=fuentes(meta): raise ValueError('Datos distintos al caché de inferencia')
        if previous['etapa']!=args.etapa: raise ValueError('Etapa distinta al caché de inferencia')
        if any(previous['codigo'].get(p)!=sha256(p) for p in BANK_CORE):
            raise ValueError('Motor experimental distinto: regenerar inferencia')
        if previous['protocolo_sha256']!=sha256(protocol_path): raise ValueError('Protocolo distinto al caché')
        for file,key in [('predicciones.csv.gz','predicciones_sha256'),('conteos_candidatos.csv.gz','conteos_sha256')]:
            if sha256(out/file)!=previous[key]: raise ValueError('Inferencia alterada')
        proof=json.loads((out/'poisson_previo.json').read_text())
        if proof['codigo_banco']!=core() or proof['datos']!=fuentes(meta):
            raise ValueError('Procedencia del banco distinta al caché')
        if sha256(out/'banco.csv.gz')!=proof['banco_sha256'] or sha256(out/'seleccion_poisson.json')!=proof['seleccion_sha256']:
            raise ValueError('Banco o selección previa alterada')
        stored=json.loads((out/'seleccion_poisson.json').read_text())
        selection,skips=stored['selecciones'],stored['omitidos']
        if args.etapa=='nb':
            nb_proof=json.loads((out/'piloto_nb.json').read_text())
            if sha256(out/'seleccion_nb.json')!=nb_proof['seleccion_nb_sha256']:
                raise ValueError('Selección NB alterada')
            selection=json.loads((out/'seleccion_nb.json').read_text())
        pred=pd.read_csv(out/'predicciones.csv.gz',parse_dates=['fecha','train_max_fecha'],float_precision='round_trip')
        diagnostic=pd.read_csv(out/'conteos_candidatos.csv.gz',parse_dates=['fecha','train_max_fecha'],float_precision='round_trip')
        validar_temporal(pred);validar_temporal(diagnostic)
        print('Reutilizando inferencia verificada; regenerando únicamente reportes...',flush=True)
    elif args.etapa=='poisson':
        inputs=[(d['archivo'],counts[counts.liga==d['liga']]) for d in meta['datos']]
        if args.procesos==1: banks=[trabajar(x) for x in inputs]
        else:
            with ProcessPoolExecutor(max_workers=min(args.procesos,len(inputs))) as pool:
                banks=list(pool.map(trabajar,inputs))
        bank=pd.concat(banks,ignore_index=True)
        bank.to_csv(out/'banco.csv.gz',index=False,float_format='%.17g',compression={'method':'gzip','mtime':0})
        selection,skips=seleccionar(bank)
        # Persistir el diagnóstico Poisson antes de permitir estimar NB.
        escribir(out/'seleccion_poisson.json',{'selecciones':selection,'omitidos':skips})
        proof={'codigo_banco':core(),'datos':fuentes(meta),'banco_sha256':sha256(out/'banco.csv.gz'),
               'seleccion_sha256':sha256(out/'seleccion_poisson.json'),'segundos_banco':time.perf_counter()-started,
               'filas_banco':len(bank),'nb_evaluada':False}
        escribir(out/'poisson_previo.json',proof)
    else:
        proof=json.loads((out/'poisson_previo.json').read_text())
        if proof['codigo_banco']!=core() or proof['datos']!=fuentes(meta): raise ValueError('Poisson previo obsoleto')
        if sha256(out/'banco.csv.gz')!=proof['banco_sha256'] or sha256(out/'seleccion_poisson.json')!=proof['seleccion_sha256']:
            raise ValueError('Banco o diagnóstico previo alterado')
        bank=pd.read_csv(out/'banco.csv.gz',parse_dates=['fecha'],float_precision='round_trip')
        stored=json.loads((out/'seleccion_poisson.json').read_text());selection,skips=stored['selecciones'],stored['omitidos']
        selection=dispersion_nb(bank,selection)
        escribir(out/'seleccion_nb.json',selection)
        # Medir la estrategia NB completa antes de la inferencia externa masiva.
        eligible=pd.concat([bank[(bank.metrica==s['metrica'])&(bank.candidato==s['candidato'])&
                    (bank.fecha.dt.to_period('M')==pd.Period(s['mes_externo']))] for s in selection],ignore_index=True)
        ids=eligible.sort_values('fecha').fixture_id.drop_duplicates().head(160)
        probe=bank[bank.fixture_id.isin(ids)]
        probe_started=time.perf_counter()
        probe_pred,probe_counts=evaluar_seleccion(probe,counts,selection,True)
        probe_seconds=time.perf_counter()-probe_started
        if probe_counts.empty: raise ValueError('Piloto NB sin cortes evaluables')
        predicted_seconds=probe_seconds*len(eligible)*3/len(probe_counts)
        escribir(out/'piloto_nb.json',{'tipo':'rendimiento; sin selección externa',
             'segundos':probe_seconds,'estimacion_segundos_predicciones':predicted_seconds,'registros_conteo':len(probe_counts),'filas_mercados':len(probe_pred),
             'alpha_max_interno':max(x['alpha'] for x in selection),'codigo_banco':core(),
             'seleccion_nb_sha256':sha256(out/'seleccion_nb.json')})
        if predicted_seconds>1800: raise ValueError('Piloto NB supera presupuesto de 30 minutos; optimizar antes de continuar')
    name='predicciones.csv.gz'
    if not args.reusar_inferencia:
        print(f'Banco: {len(bank):,}; {len(selection)} selecciones externas. Generando probabilidades...',flush=True)
        pred,diagnostic=evaluar_seleccion(bank,counts,selection,args.etapa=='nb')
        if pred.empty: raise ValueError('Validación interna insuficiente: no hay meses externos evaluables')
        pred.to_csv(out/name,index=False,float_format='%.17g',compression={'method':'gzip','mtime':0})
        diagnostic.to_csv(out/'conteos_candidatos.csv.gz',index=False,float_format='%.17g',compression={'method':'gzip','mtime':0})
    from .reportes import generar
    if core()!=protocol['codigo_banco'] or any(sha256(d['archivo'])!=d['sha256'] for d in meta['datos']):
        raise ValueError('Código o datos cambiaron durante la ejecución')
    manifest={'version':VERSION,'etapa':args.etapa,'datos':meta['datos'],'fase2_codigo':meta['codigo_sha256'],
              'codigo':{str(p):sha256(p) for p in sorted(Path('experimentos').glob('*.py'))},
              'predicciones_sha256':sha256(out/name),'conteos_sha256':sha256(out/'conteos_candidatos.csv.gz'),
              'banco_sha256':proof['banco_sha256'],'seleccion_poisson_sha256':proof['seleccion_sha256'],
              'protocolo':'nested temporal mensual; 3 meses internos OOS anteriores; embargo 1 día',
              'min_partidos_internos':100,'min_meses_internos':2,'criterio':'Brier primario macro por liga; desempate ID',
              'primarios':{'tiros':'OU local','tiros_a_puerta':'OU total','goles':'OU total','goles_1t':'OU total',
                           'goles_2t':'OU total','amarillas':'OU total','corners':'OU total'},
              'independiente':False,'periodo_independiente':'futuro tras cierre del protocolo y registro antes del kickoff',
              'calibracion_en_produccion':False,'modelo_produccion_modificado':False,'cuotas_verificadas':False,
              'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,
              'scipy':scipy.__version__,'matplotlib':matplotlib.__version__,'protocolo_sha256':sha256(protocol_path),
              'semilla':20261011,'replicas_bootstrap':2000,'procesos':args.procesos,
              'reusar_inferencia':args.reusar_inferencia}
    generar(out,pred,diagnostic,counts,Path(args.cache_fase2),meta,selection,skips,manifest)
    manifest['segundos_total']=time.perf_counter()-started
    if previous is not None:
        manifest['segundos_evaluacion_original']=previous.get('segundos_evaluacion_original',previous['segundos_total'])
    escribir(out/'manifest.json',manifest)
    print(f'Completado {args.etapa} en {manifest["segundos_total"]:.1f}s: {out}/REPORTE.md',flush=True)


if __name__=='__main__': main()

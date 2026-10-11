"""CLI reproducible: python -m evaluacion --salida docs/fase2."""
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

import modelo as mo
import probabilidades as pr
from .datos import cargar, inventario, METRICAS, sha256
from .temporal import ejecutar_liga
from .metricas import puntuar, muestra_comun
from .calibradores import temporal
from .reportes import generar

CORE = ('modelo.py','probabilidades.py','kuota.py','evaluacion/datos.py',
        'evaluacion/temporal.py','evaluacion/mercados.py')


def recuperar(out, inventory):
    """Reusar únicamente registros propios cuya procedencia y hashes coinciden."""
    manifest=json.loads((out/'manifest.json').read_text())
    if [d['sha256'] for d in inventory] != [d['sha256'] for d in manifest['datos']]:
        raise ValueError('Los datos cambiaron: hay que regenerar predicciones')
    if any(manifest['codigo_sha256'].get(p)!=sha256(p) for p in CORE):
        raise ValueError('El motor cambió: hay que regenerar predicciones')
    for name in ('predicciones.csv.gz','predicciones_conteos.csv.gz','abstenciones.csv'):
        expected=manifest.get('artefactos_sha256',{}).get(name)
        if not expected or sha256(out/name)!=expected:
            raise ValueError(f'Cache sin hash válido: {name}')
    pred=pd.read_csv(out/'predicciones.csv.gz',parse_dates=['fecha','train_max_fecha'],float_precision='round_trip')
    counts=pd.read_csv(out/'predicciones_conteos.csv.gz',parse_dates=['fecha','train_max_fecha'],float_precision='round_trip')
    abst=pd.read_csv(out/'abstenciones.csv')
    if (pred.train_max_fecha>=pred.fecha).any() or (counts.train_max_fecha>=counts.fecha).any():
        raise ValueError('Cache con corte temporal inválido')
    return pred,counts,abst


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--datos',nargs='+',default=sorted(str(p) for p in Path('datos').glob('bbdd_*.csv')))
    parser.add_argument('--salida',default='docs/fase2')
    parser.add_argument('--procesos',type=int,default=2)
    parser.add_argument('--holdout-desde',default='2026-07-01')
    parser.add_argument('--guardar-predicciones',action='store_true')
    parser.add_argument('--reusar-predicciones',action='store_true')
    args=parser.parse_args(argv)
    if not args.datos: parser.error('No hay archivos de datos')
    if args.procesos<1: parser.error('--procesos debe ser >=1')
    pd.Timestamp(args.holdout_desde)
    out=Path(args.salida);out.mkdir(parents=True,exist_ok=True)
    inventory=[inventario(p,cargar(p)) for p in args.datos]
    if len({entry['liga'] for entry in inventory})!=len(inventory):
        raise ValueError('Ligas duplicadas: usar un solo histórico consolidado por liga')
    started=time.monotonic()
    if args.reusar_predicciones:
        pred,count,abstentions=recuperar(out,inventory)
    else:
        parts=[];counts=[];abst=[]
        if args.procesos==1:
            for path in args.datos:
                p,c,a=ejecutar_liga(path)
                parts.append(p);counts.append(c);abst.append(a)
                print(f'{path}: {len(p):,} registros de mercados; {len(c):,} de conteos',flush=True)
        else:
            with ProcessPoolExecutor(max_workers=min(args.procesos,len(args.datos))) as pool:
                for path,(p,c,a) in zip(args.datos,pool.map(ejecutar_liga,args.datos)):
                    parts.append(p);counts.append(c);abst.append(a)
                    print(f'{path}: {len(p):,} registros de mercados; {len(c):,} de conteos',flush=True)
        pred=pd.concat(parts,ignore_index=True)
        count=pd.concat(counts,ignore_index=True)
        abstentions=pd.concat(abst,ignore_index=True)
        del parts,counts,abst
    if pred.empty: raise ValueError('Ningún partido tiene historial evaluable')
    if any(sha256(p)!=entry['sha256'] for p,entry in zip(args.datos,inventory)):
        raise ValueError('Los datos cambiaron durante la ejecución')
    for col in ('liga','temporada','metrica','modelo','kind','lado','observado','local','visitante'):
        pred[col]=pred[col].astype('category')
    artifacts={}
    if args.guardar_predicciones and not args.reusar_predicciones:
        pred.to_csv(out/'predicciones.csv.gz',index=False,compression={'method':'gzip','mtime':0},float_format='%.17g')
        count.to_csv(out/'predicciones_conteos.csv.gz',index=False,compression={'method':'gzip','mtime':0},float_format='%.17g')
    abstentions.to_csv(out/'abstenciones.csv',index=False,float_format='%.10g')
    if args.guardar_predicciones or args.reusar_predicciones:
        artifacts={name:sha256(out/name) for name in ('predicciones.csv.gz','predicciones_conteos.csv.gz','abstenciones.csv')}
    common=muestra_comun(pred)
    scored=puntuar(common)
    print(f'Muestra común: {len(scored):,} registros. Calibración mensual...',flush=True)
    calibrated,fits,skips=temporal(common)
    manifest={'tipo':'retrospectivo_con_estadisticas_actuales; no replay as-of certificado',
              'version_motor':pr.VERSION,'parametros':{'XI':mo.XI,'RHO':mo.RHO,'K_ENCOGE':mo.K_ENCOGE,'PJ_MIN':mo.PJ_MIN},
              'metricas':list(METRICAS),'holdout_desde':args.holdout_desde,'semilla_bootstrap':20261010,
              'bootstrap_replicas':1000,'logloss_epsilon_diagnostico':1e-15,
              'platt_isotonica_min_partidos':100,'platt_isotonica_min_clase':20,'embargo_calibracion_dias':1,
              'datos':inventory,'filas_mercados':len(pred),'filas_comunes':len(common),'filas_conteos':len(count),
              'codigo_sha256':{str(p):sha256(p) for p in [Path('modelo.py'),Path('probabilidades.py'),Path('kuota.py'),*sorted(Path('evaluacion').glob('*.py'))]},
              'artefactos_sha256':artifacts,
              'entorno':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,
                         'scipy':scipy.__version__,'matplotlib':matplotlib.__version__},
              'comando':{'datos':args.datos,'salida':args.salida,'procesos':args.procesos,
                         'guardar_predicciones':args.guardar_predicciones,'reusar_predicciones':args.reusar_predicciones},
              'cuotas_verificadas':False,'calibracion_en_produccion':False}
    print(f'{len(fits)} ajustes temporales. Generando tablas y figuras...',flush=True)
    comparisons,_=generar(out,scored,count,abstentions,inventory,manifest,calibrated,fits,skips)
    print(comparisons.to_string(index=False),flush=True)
    print(f'Completado en {time.monotonic()-started:.1f}s. Reporte: {out}/REPORTE.md',flush=True)


if __name__=='__main__': main()

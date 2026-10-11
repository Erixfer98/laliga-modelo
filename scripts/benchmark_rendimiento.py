"""Benchmark reproducible: referencia git sin modificar fórmulas vs rama actual.
Uso: python scripts/benchmark_rendimiento.py --reference c31f6cf --output work/rendimiento/servidor.json
No usar conjuntamente con pruebas/navegadores: evitar contención de CPU.
"""
import argparse
import json
import subprocess
import sys
import time
import types
import functools
import resource
from collections import defaultdict
from fastapi.responses import JSONResponse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import api
import modelo
import probabilidades
import kuota
from fastapi.testclient import TestClient


def cargar_ref(nombre,archivo,ref):
    fuente=subprocess.check_output(['git','show',f'{ref}:{archivo}'],text=True)
    modulo=types.ModuleType(nombre);exec(compile(fuente,archivo,'exec'),modulo.__dict__)
    return modulo


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--reference',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    referencia=cargar_ref('kuota_referencia','kuota.py',args.reference)
    vieja=cargar_ref('api_referencia','api.py',args.reference);vieja.kuota=referencia
    filas=[]
    tiempos=defaultdict(float);cuentas=defaultdict(int);profundidad=defaultdict(int)
    def instrumentar(modulo,nombre,label):
        original=getattr(modulo,nombre)
        @functools.wraps(original)
        def medir(*a,**kw):
            externa=profundidad[label]==0;profundidad[label]+=1;t=time.perf_counter()
            try:return original(*a,**kw)
            finally:
                profundidad[label]-=1
                if externa:tiempos[label]+=(time.perf_counter()-t)*1000;cuentas[label]+=1
        setattr(modulo,nombre,medir)
    for modulo,nombre,label in [(modelo,'fuerzas','fuerzas'),(modelo,'lambdas','lambdas'),(probabilidades,'distribucion','distribuciones'),(JSONResponse,'render','serializacion')]:
        instrumentar(modulo,nombre,label)
    for modulo in [referencia,kuota]:
        for nombre,label in [('mercados','mercados'),('grafico_modelo','graficos'),('stats_historial','detalle'),('a_json','conversion_json')]:instrumentar(modulo,nombre,label)

    for etiqueta,modulo in [('antes',vieja),('despues',api)]:
        client=TestClient(modulo.app)
        for met in ['goles','corners','tiros']:
            for caso,extra in [('fria',{}),('repetida',{}),('grupo',{'grupo':'Total'}),('mercado',{'pata':'Total Over 2.5'}),('lineas',{'cfg':json.dumps({'Total':[3.5,1],'Real Madrid':[1.5,1],'Alaves':[.5,1]})})]:
                for repeticion in range(1 if caso=='fria' else 10):
                    tiempos.clear();cuentas.clear();t=time.perf_counter();r=client.get('/liga/laliga/partido',params={'local':'Real Madrid','visitante':'Alaves','met':met,**extra});ms=(time.perf_counter()-t)*1000
                    assert r.status_code==200,r.text
                    filas.append({'version':etiqueta,'met':met,'case':caso,'repeat':repeticion,'http_ms':ms,'bytes':len(r.content),'server_timing':r.headers.get('server-timing'),'stages_ms':dict(tiempos),'calls':dict(cuentas)})
            if etiqueta=='despues':
                for modo in ['resumen','detalle']:
                    for i in range(10):
                        tiempos.clear();cuentas.clear();t=time.perf_counter();r=client.get('/liga/laliga/partido',params={'local':'Real Madrid','visitante':'Alaves','met':met,'modo':modo});ms=(time.perf_counter()-t)*1000
                        filas.append({'version':etiqueta,'met':met,'case':modo,'repeat':i,'http_ms':ms,'bytes':len(r.content),'server_timing':r.headers.get('server-timing'),'stages_ms':dict(tiempos),'calls':dict(cuentas)})
    # Comparación real del código anterior completo, no solamente del recorrido actual sin caché.
    equivalencias=[]
    for liga in kuota.LIGAS:
        try:df=kuota.cargar(liga)
        except FileNotFoundError:continue
        equipos=kuota.equipos(df);local,visitante=equipos[:2]
        for met in kuota.NOM:
            inc=kuota.incertidumbre(df,met)
            for cfg in [None,{'Total':[2.,1],local:[1.5,0],visitante:[0.,1]}]:
                old=referencia.a_json(referencia.vista_partido(df,liga,local,visitante,met,inc,cfg))
                params={'local':local,'visitante':visitante,'met':met}
                if cfg:params['cfg']=json.dumps(cfg)
                new=TestClient(api.app).get(f'/liga/{liga}/partido',params=params).json();new.pop('data_version')
                assert old==new,(liga,met,cfg)
                equivalencias.append({'liga':liga,'met':met,'cfg':cfg,'mercados':len(old['mercados']),'coincidencia':'exacta'})
    destino=Path(args.output);destino.parent.mkdir(parents=True,exist_ok=True)
    destino.write_text(json.dumps({'reference':args.reference,'timings':filas,'equivalence':equivalencias,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'cache_estimated_bytes':{'modelos':api._modelos.bytes,'mercados':api._mercados.bytes,'vistas':api._vistas.bytes}},indent=2))
    print(f'{len(filas)} mediciones; {len(equivalencias)} contextos coinciden exactamente',flush=True)

if __name__=='__main__':main()

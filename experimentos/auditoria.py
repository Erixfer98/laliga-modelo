"""Auditoría reproducible de cortes contra futuro perturbado y prefijos causales.

Ejecutar desde la raíz del repositorio: python -m experimentos.auditoria
Requiere el banco detallado regenerable, que no se versiona.
"""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from experimentos.temporal import seleccionar,dispersion_nb


def main():
    root=Path('docs/fase3')
    bank=pd.read_csv(root/'banco.csv.gz',parse_dates=['fecha'],float_precision='round_trip')
    original=json.loads((root/'seleccion_nb.json').read_text())
    checked=[]
    for met,g in bank.groupby('metrica',observed=True):
        fits,_=seleccionar(g);fits=dispersion_nb(g,fits)
        for expected in fits:
            month=expected['mes_externo'];cut=pd.Timestamp(expected['cutoff_exclusivo'])
            changed=g.copy();future=changed.fecha>=cut
            changed.loc[future,['real_local','real_visitante']]=[500.,0.]
            changed.loc[future,['lambda_local','lambda_visitante']]=[.001,900.]
            changed.loc[future,'brier_interno']=np.arange(future.sum())%26
            new,_=seleccionar(changed)
            selected=next(f for f in new if f['mes_externo']==month)
            actual=dispersion_nb(changed,[selected])[0]
            assert actual==expected,(met,month,'perturbacion')
            first=g.loc[g.fecha.dt.to_period('M')==pd.Period(month),'fecha'].min()
            prefix=g[(g.fecha<cut)|(g.fecha==first)]
            partial,_=seleccionar(prefix)
            selected=next(f for f in partial if f['mes_externo']==month)
            assert dispersion_nb(prefix,[selected])[0]==expected,(met,month,'prefijo')
            saved=next(f for f in original if f['metrica']==met and f['mes_externo']==month)
            assert saved==expected,(met,month,'artefacto')
            checked.append({'metrica':met,'mes_externo':month,'cutoff_exclusivo':str(cut.date()),'alpha':expected['alpha'],'nb_habilitada':expected['nb_habilitada']})
        print(f'{met}: {len(fits)} cortes verificados',flush=True)
    result={'cortes':len(checked),'nb_habilitada':sum(f['nb_habilitada'] for f in checked),'perturbacion_futuro_embargo_invariante':True,'prefijo_causal_invariante':True,'seleccion_persistida_identica':True,'detalle':checked}
    result['entradas_sha256']={name:hashlib.sha256((root/name).read_bytes()).hexdigest()
                              for name in ('banco.csv.gz','seleccion_nb.json','protocolo.json')}
    result['codigo_sha256']={str(p.relative_to(Path.cwd())) if p.is_absolute() else str(p):hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in (Path(__file__),Path('experimentos/temporal.py'),
                                      Path('experimentos/lambdas.py'),Path('experimentos/distribuciones.py'))}
    Path('docs/fase3/auditoria_temporal_final.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='detalle'}))


if __name__=='__main__': main()

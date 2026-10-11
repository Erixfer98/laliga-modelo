"""Walk-forward por fecha de fuente. Reutiliza fuerzas y distribución Fase 1."""
import math

import numpy as np
import pandas as pd
from scipy.stats import poisson

import modelo as mo
import probabilidades as pr
from .datos import cargar, METRICAS
from .mercados import registro, probabilidades, observado

MODELOS = ('actual','sin_dc','liga','movil_10')


def lambdas_referencia(hist, met, local, visitante, f):
    cl,cv,_ = mo.METRICAS[met]
    league = (float(f.attrs['prom_casa']),float(f.attrs['prom_fuera']))
    # Últimos 10 partidos en la condición, sin multiplicar ataque por defensa.
    home = hist[hist.equipo_local_txt==local][cl].tail(10)
    away = hist[hist.equipo_visitante_txt==visitante][cv].tail(10)
    moving = (float(home.mean()) if len(home) else league[0],
              float(away.mean()) if len(away) else league[1])
    return league, moving


def ejecutar_liga(path, metricas=METRICAS):
    d = cargar(path); preds=[]; counts=[]; abst=[]; columns=None
    for date, today in d.groupby('fecha',sort=True):
        hist = d[d.fecha<date].copy()
        if hist.empty:
            for fixture in today.fixture_id:
                abst.append({'fixture_id':fixture,'liga':d.liga.iloc[0],'fecha':date,'metrica':'todas',
                             'motivo':'sin_historial_liga'})
            continue
        hist['peso'] = np.exp(-mo.XI*(date-hist.fecha).dt.days)
        home = hist.equipo_local_txt.value_counts(); away=hist.equipo_visitante_txt.value_counts()
        for met in metricas:
            cl,cv,dc = mo.METRICAS[met]
            try:
                f = mo.fuerzas(hist,met)
            except ValueError as exc:
                for fixture in today.fixture_id:
                    abst.append({'fixture_id':fixture,'liga':d.liga.iloc[0],'fecha':date,'metrica':met,'motivo':str(exc)})
                continue
            for _, match in today.iterrows():
                h,v = match.equipo_local_txt,match.equipo_visitante_txt
                if h not in f.index or v not in f.index:
                    abst.append({'fixture_id':match.fixture_id,'liga':match.liga,'fecha':date,'metrica':met,
                                 'motivo':'equipo_sin_historial; sin fallback del modelo actual'})
                    continue
                ll,lv = mo.lambdas(f,h,v)
                lg,moving = lambdas_referencia(hist,met,h,v,f)
                parameters = {'actual':(ll,lv,dc),'sin_dc':(ll,lv,False),
                              'liga':(*lg,False),'movil_10':(*moving,False)}
                markets = registro(met,ll,lv)  # misma selección para los cuatro comparadores
                eff=[]
                for col,team in [('equipo_local_txt',h),('equipo_visitante_txt',v)]:
                    w=hist.loc[hist[col]==team,'peso'].to_numpy()
                    eff.append(float(w.sum()**2/np.dot(w,w)) if len(w) else 0.)
                base = {'fixture_id':match.fixture_id,'liga':match.liga,'temporada':match.temporada_txt,
                        'fecha':date,'train_max_fecha':hist.fecha.max(),'local':h,'visitante':v,'metrica':met,
                        'n_casa':int(home.get(h,0)),'n_fuera':int(away.get(v,0)),
                        'n_eff_min':min(eff),'maduro':min(home.get(h,0),away.get(v,0))>=mo.PJ_MIN,
                        'maduro_efectivo':min(eff)>=mo.PJ_MIN}
                x,y=int(match[cl]),int(match[cv])
                for name,(a,b,use_dc) in parameters.items():
                    try:
                        m,metadata=pr.distribucion(a,b,use_dc,mo.RHO,mo.K_MAX[met])
                    except ValueError as exc:
                        abst.append({**base,'modelo':name,'motivo':str(exc)})
                        continue
                    tau=mo.tau(x,y,a,b,mo.RHO) if use_dc else 1.
                    logp=float(poisson.logpmf(x,a)+poisson.logpmf(y,b))
                    logp += math.log(tau) if tau>0 else -math.inf
                    # Likelihood del proceso no truncado; no silenciar ceros estructurales.
                    tail = {}
                    margins = {'local':m.sum(axis=1),'visitante':m.sum(axis=0),
                               'total':np.bincount(np.add.outer(np.arange(len(m)),np.arange(len(m))).ravel(),weights=m.ravel())}
                    for side,pmf in margins.items():
                        value = {'local':x,'visitante':y,'total':x+y}[side]
                        for q in (95,99):
                            threshold = int(np.searchsorted(np.cumsum(pmf),q/100))
                            tail[f'extremo_{side}_{q}'] = value>threshold
                            tail[f'p_extremo_{side}_{q}'] = float(pmf[threshold+1:].sum())
                    counts.append({**base,**tail,'modelo':name,'lambda_local':a,'lambda_visitante':b,
                                   'real_local':x,'real_visitante':y,'nll_conjunta':-logp,
                                   'fuera_soporte':x>=len(m) or y>=len(m),
                                   'k_max':metadata['k_max'],'masa_excluida':metadata['masa_excluida']})
                    ps=probabilidades(m,markets)
                    for market,p in zip(markets,ps):
                        yy=observado(market,x,y)
                        labels=('visitante','empate','local') if market['kind']=='1x2' else ('fallo','push','acierto')
                        if market['kind']=='btts': labels=('no','no_aplica','si')
                        record = {**base,'modelo':name,**{k:val for k,val in market.items() if k!='regla'},
                                      'p0':p[0],'p1':p[1],'p2':p[2],'y':yy,'observado':labels[yy],
                                      'conteo':{'total':x+y,'local':x,'visitante':y}[market['lado']]}
                        if columns is None: columns = list(record)
                        preds.append(tuple(record.values()))
    return pd.DataFrame.from_records(preds,columns=columns),pd.DataFrame(counts),pd.DataFrame(abst)

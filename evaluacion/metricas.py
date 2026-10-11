"""Scores propios, segmentos y diferencias emparejadas con bootstrap semanal."""
import numpy as np
import pandas as pd
import modelo as mo

EPS = 1e-15


def puntuar(pred):
    d=pred.copy()
    p=d[['p0','p1','p2']].to_numpy(float); y=d.y.to_numpy(int)
    if not np.isfinite(p).all() or (p < 0).any() or not np.allclose(p.sum(axis=1),1.,atol=1e-12,rtol=0.):
        raise ValueError('Vector de probabilidades inválido')
    if not np.isin(y,[0,1,2]).all(): raise ValueError('Clase observada inválida')
    onehot=np.eye(3)[y]
    d['brier']=.5*np.square(p-onehot).sum(axis=1)
    observed=p[np.arange(len(d)),y]
    d['cero_observado']=observed==0
    d['logloss_clip']=-np.log(np.maximum(observed,EPS))
    d['logloss']=np.where(observed>0,-np.log(np.maximum(observed,np.finfo(float).tiny)),np.inf)
    return d


def muestra_comun(pred):
    keys=['fixture_id','metrica','kind','lado','linea']
    size=pred.groupby(keys,observed=True).modelo.transform('nunique')
    return pred[size==4].copy()


def resumen(d, keys):
    if d.empty: return pd.DataFrame()
    return d.groupby(keys,observed=True,dropna=False).agg(
        partidos=('fixture_id','nunique'), selecciones=('fixture_id','size'),
        brier=('brier','mean'),logloss=('logloss','mean'),logloss_clip=('logloss_clip','mean'),
        ceros_observados=('cero_observado','sum'),
        pushes=('es_push','sum') if 'es_push' in d else ('cero_observado',lambda s:0)
    ).reset_index().assign(logloss=lambda r:np.where(r.ceros_observados>0,np.inf,r.logloss))


def eventos(d):
    """One-vs-rest por clase; no confunde empate de 1X2 con push de OU."""
    parts=[]
    for cls in (0,1,2):
        eligible = np.ones(len(d),dtype=bool)
        if cls==1:
            eligible=(d.kind=='1x2')|((d.kind=='ou')&(d.linea%1==0))
        s=d.loc[eligible].copy()
        s['p']=s[f'p{cls}'];s['hit']=(s.y==cls).astype(int)
        label = {0:'Under',1:'Push',2:'Over'}[cls]
        s['evento']=np.where(s.kind=='1x2',{0:'Visitante',1:'Empate',2:'Local'}[cls],
                            np.where(s.kind=='btts',{0:'No',1:'No aplica',2:'Sí'}[cls],label))
        parts.append(s)
    return pd.concat(parts,ignore_index=True)


def calibracion(d, keys):
    e=eventos(d)
    e['bin']=pd.cut(e.p,bins=[i/10 for i in range(11)],include_lowest=True,right=False)
    # El 100% pertenece al último intervalo, no se pierde.
    e.loc[e.p==1,'bin']=e['bin'].cat.categories[-1]
    g=e.groupby(keys+['evento','bin'],observed=True).agg(
        selecciones=('p','size'),partidos=('fixture_id','nunique'),p_media=('p','mean'),
        frecuencia=('hit','mean'),positivos=('hit','sum')).reset_index()
    g['gap']=g.frecuencia-g.p_media
    # Wilson es descriptivo por bin. Inferencia comparativa usa bloques, no patas iid.
    n=g.selecciones;z=1.959963984540054; center=(g.frecuencia+z*z/(2*n))/(1+z*z/n)
    radius=z*np.sqrt(g.frecuencia*(1-g.frecuencia)/n+z*z/(4*n*n))/(1+z*z/n)
    g['wilson_lo']=center-radius;g['wilson_hi']=center+radius
    g['bin']=g['bin'].astype(str)
    return g


def bootstrap_pareado(d, replicas=1000, seed=20261010, referencias=('sin_dc','liga','movil_10')):
    # Igual peso para partidos, no para su número de líneas.
    per=d.groupby(['fixture_id','fecha','metrica','modelo'],observed=True).brier.mean().unstack('modelo').reset_index()
    rng=np.random.default_rng(seed); rows=[]
    for met,g in per.groupby('metrica',observed=True):
        for ref in referencias:
            s=g.dropna(subset=['actual',ref]).copy()
            s['diff']=s.actual-s[ref]
            s['week']=pd.to_datetime(s.fecha).dt.to_period('W-SUN').astype(str)
            blocks=s.groupby('week').agg(total=('diff','sum'),n=('diff','size'))
            draws=rng.integers(0,len(blocks),(replicas,len(blocks)))
            vals=blocks.total.to_numpy()[draws].sum(axis=1)/blocks.n.to_numpy()[draws].sum(axis=1)
            lo,hi=np.quantile(vals,[.025,.975])
            rows.append({'metrica':met,'referencia':ref,'partidos':len(s),'bloques':len(blocks),
                         'delta_brier':s['diff'].mean(),'ic95_lo':lo,'ic95_hi':hi})
    return pd.DataFrame(rows)


def diagnostico_conteos(counts):
    rows=[]
    for (met,model,league),g in counts[counts.maduro].groupby(['metrica','modelo','liga'],observed=True):
        for side in ('local','visitante','total'):
            x=(g.real_local+g.real_visitante).to_numpy() if side=='total' else g[f'real_{side}'].to_numpy()
            lam=(g.lambda_local+g.lambda_visitante).to_numpy() if side=='total' else g[f'lambda_{side}'].to_numpy()
            var=lam.copy()
            if side=='total' and model=='actual' and met in ('goles','goles_1t'):
                var=var-2*mo.RHO*g.lambda_local.to_numpy()*g.lambda_visitante.to_numpy()*np.exp(-lam)
            squared=np.square(x-lam)
            pearson=np.divide(squared,var,out=np.zeros_like(lam),where=var>0)
            pearson[(var==0)&(x>0)]=np.inf
            nll=g.nll_conjunta.to_numpy()
            row={'metrica':met,'modelo':model,'liga':league,'lado':side,'partidos':len(g),
                 'media_real':x.mean(),'media_predicha':lam.mean(),'mae':np.abs(x-lam).mean(),
                 'rmse':np.sqrt(squared.mean()),'sesgo':(lam-x).mean(),'pearson_condicional':pearson.mean(),
                 'varianza_marginal_real':x.var(ddof=1),'varianza_modelada_media':var.mean(),
                 'nll_conjunta':np.inf if np.isinf(nll).any() else nll.mean(),
                 'ceros_estructurales_conjuntos':int(np.isinf(nll).sum()),
                 'fuera_soporte':int(g.fuera_soporte.sum())}
            for q in ('95','99'):
                row[f'cola_{q}_real']=g[f'extremo_{side}_{q}'].mean()
                row[f'cola_{q}_pred']=g[f'p_extremo_{side}_{q}'].mean()
            rows.append(row)
    return pd.DataFrame(rows)


def bootstrap_mercados(d, replicas=1000):
    """Diferencias por familia/lado, con partidos y semanas como unidades."""
    parts=[]
    for (kind,side),g in d.groupby(['kind','lado'],observed=True):
        b=bootstrap_pareado(g,replicas=replicas)
        b['kind']=kind;b['lado']=side;parts.append(b)
    return pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()

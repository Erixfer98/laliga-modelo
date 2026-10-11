"""Platt e isotónica experimentales, entrenados antes de cada mes de prueba."""
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit
from .comparabilidad import validar_temporal


def fit_platt(p,y,w=None):
    w=np.ones(len(y)) if w is None else np.asarray(w)
    x=logit(np.clip(p,1e-6,1-1e-6));y=np.asarray(y,float)
    def objective(theta):
        z=theta[0]*x+theta[1]
        loss=np.dot(w,np.logaddexp(0,z)-y*z)/w.sum()
        residual=w*(expit(z)-y)/w.sum()
        return loss,np.array([np.dot(residual,x),residual.sum()])
    r=minimize(objective,[1.,0.],jac=True,bounds=[(0.,20.),(-20.,20.)],method='L-BFGS-B')
    if not r.success: raise ValueError('Platt no converge')
    return {'a':float(r.x[0]),'b':float(r.x[1])}


def fit_isotonica(p,y,w=None):
    # PAVA con agrupación previa de empates. Sin dependencia sklearn.
    w=np.ones(len(y)) if w is None else np.asarray(w)
    frame=pd.DataFrame({'p':p,'wy':np.asarray(y)*w,'w':w})
    agg=frame.groupby('p',sort=True).sum();blocks=[]
    for x,row in agg.iterrows():
        blocks.append([x,x,float(row.wy),float(row.w)])
        while len(blocks)>1 and blocks[-2][2]/blocks[-2][3]>blocks[-1][2]/blocks[-1][3]:
            right=blocks.pop();left=blocks.pop()
            blocks.append([left[0],right[1],left[2]+right[2],left[3]+right[3]])
    # Cada punto de entrenamiento recibe la media de su bloque; interpolación monótona.
    xs=[];ys=[]
    for lo,hi,sy,sw in blocks:
        xs.extend([lo,hi]);ys.extend([sy/sw,sy/sw])
    return {'x':xs,'y':ys}


def aplicar(method,model,p):
    if method=='platt': return expit(model['a']*logit(np.clip(p,1e-6,1-1e-6))+model['b'])
    return np.interp(p,model['x'],model['y'])


def temporal(pred,min_partidos=100,min_clase=20):
    validar_temporal(pred)
    d=pred[(pred.modelo=='actual')&pred.maduro&pred.fija&
           ((pred.kind=='btts')|((pred.kind=='ou')&(pred.linea%1==.5)))].copy()
    d['mes']=pd.to_datetime(d.fecha).dt.to_period('M')
    result=[];fits=[];skips=[]
    for (met,side,kind),g in d.groupby(['metrica','lado','kind'],observed=True):
        for month in sorted(g.mes.unique()):
            # Embargo de un día adicional: fechas de fuente no son timestamps UTC completos.
            cutoff=month.start_time-pd.Timedelta(days=1)
            train=g[g.fecha<cutoff].copy();test=g[g.mes==month].copy()
            target=(train.y==2).astype(int)
            n=train.fixture_id.nunique();positive=train.loc[target==1,'fixture_id'].nunique()
            negative=train.loc[target==0,'fixture_id'].nunique()
            meta={'metrica':met,'lado':side,'kind':kind,'mes_test':str(month),'n_train':n,
                  'train_max_fecha':str(train.fecha.max().date()) if len(train) else None,
                  'test_min_fecha':str(test.fecha.min().date()),'embargo_dias':1}
            if n<min_partidos or positive<min_clase or negative<min_clase:
                skips.append({**meta,'motivo':'historial de calibración insuficiente'})
                continue
            weights=1/train.groupby('fixture_id').fixture_id.transform('size').to_numpy()
            for method,fit in [('platt',fit_platt),('isotonica',fit_isotonica)]:
                model=fit(train.p2.to_numpy(),target.to_numpy(),weights)
                q=aplicar(method,model,test.p2.to_numpy())
                calibrated=test.copy();calibrated['modelo']=method
                calibrated['p2']=q;calibrated['p0']=1-q;calibrated['p1']=0.
                result.append(calibrated.drop(columns='mes'))
                fits.append({**meta,'metodo':method,'parametros':model})
    return (pd.concat(result,ignore_index=True) if result else pd.DataFrame(),fits,skips)

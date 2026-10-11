"""Poisson/DC y NB2 experimentales, con probabilidades marginales analíticas."""
import numpy as np
from scipy.stats import poisson, nbinom
from scipy.optimize import minimize_scalar
import modelo as mo
from evaluacion.mercados import observado

TOL_COLA=1e-12
MAX_K=4096


def validar_dc(ll,lv,rho):
    if min(1-ll*lv*rho,1+ll*rho,1+lv*rho,1-rho) <= 0:
        raise ValueError('DC experimental fuera de dominio estrictamente positivo')


def correccion_cdf(t,c):
    return np.where(t==0,-c,np.where(t==1,c,0.))


def primaria(metrica):
    return 'local' if metrica=='tiros' else 'total'


def score_primario(ll,lv,x,y,lines,side='total',rho=0.):
    """Vectoriza todos los candidatos. OU analítico no inventa ceros por soporte."""
    ll,lv=np.asarray(ll),np.asarray(lv)
    lam={'local':ll,'visitante':lv,'total':ll+lv}[side][:,None]
    lines=np.asarray(lines)[None,:]
    under=poisson.cdf(np.ceil(lines)-1,lam)
    over=poisson.sf(np.floor(lines),lam)
    push=np.where(lines%1==0,poisson.pmf(lines,lam),0.)
    if side=='total':
        rho=np.broadcast_to(rho,ll.shape)
        for a,b,r in zip(ll,lv,rho): validar_dc(a,b,r)
        c=(rho*ll*lv*np.exp(-ll-lv))[:,None]
        under+=correccion_cdf(np.ceil(lines)-1,c)
        over-=correccion_cdf(np.floor(lines),c)
        push+=np.where(lines%1==0,np.where(lines==0,-c,np.where(lines==1,2*c,np.where(lines==2,-c,0.))),0.)
    p=np.stack([under,push,over],axis=-1)
    if (p < -1e-14).any() or not np.allclose(p.sum(axis=-1),1,atol=1e-12,rtol=0):
        raise ValueError('Probabilidad primaria inválida')
    p=np.maximum(p,0);p/=p.sum(axis=-1,keepdims=True)
    value={'local':x,'visitante':y,'total':x+y}[side]
    target=np.where(value>lines,2,np.where(value==lines,1,0)).ravel()
    brier=.5*np.square(p-np.eye(3)[target][None,:,:]).sum(axis=-1).mean(axis=1)
    return brier


def ajustar_alpha(train):
    """MLE de dispersión sobre predicciones internas OOS, no sobre medias in-sample."""
    lam=np.concatenate([train.lambda_local,train.lambda_visitante])
    x=np.concatenate([train.real_local,train.real_visitante])
    def loss(a):
        if a < 1e-8: return -poisson.logpmf(x,lam).mean()
        return -nbinom.logpmf(x,1/a,1/(1+a*lam)).mean()
    fit=minimize_scalar(loss,bounds=(1e-7,2.),method='bounded',options={'xatol':1e-6})
    if not fit.success: raise ValueError('No converge dispersión NB')
    return float(fit.x) if fit.fun < loss(0) else 0.


def marginal(lam,alpha=0.):
    if not np.isfinite(lam) or lam<=0 or not np.isfinite(alpha) or alpha<0:
        raise ValueError('Parámetros de distribución inválidos')
    return poisson(lam) if alpha<1e-8 else nbinom(1/alpha,1/(1+alpha*lam))


def predecir(ll,lv,markets,x,y,rho=0.,alpha=0.):
    if alpha and rho: raise ValueError('DC no está definido para NB')
    validar_dc(ll,lv,rho)
    dl,dv=marginal(ll,alpha),marginal(lv,alpha)
    # Incluye todas las líneas para conservar masa positiva de eventos raros.
    minimum=int(max(m['linea'] for m in markets if m['kind']=='ou'))+8
    k=max(minimum,int(dl.isf(TOL_COLA/2)),int(dv.isf(TOL_COLA/2)))
    if k>MAX_K: raise ValueError('Soporte experimental excedido; no excluir silenciosamente')
    pl,pv=dl.pmf(np.arange(k+1)),dv.pmf(np.arange(k+1))
    total=np.convolve(pl,pv)
    c=rho*ll*lv*np.exp(-ll-lv)
    total[:3]+=np.array([-c,2*c,-c])
    draw=float(np.dot(pl,pv)-2*c)
    home=float(np.dot(pl,np.r_[0.,np.cumsum(pv)[:-1]])+c)
    away=float(np.dot(pv,np.r_[0.,np.cumsum(pl)[:-1]])+c)
    btts=float(pl[1:].sum()*pv[1:].sum()-c)
    distributions={'local':dl,'visitante':dv,'total':poisson(ll+lv)}
    ou={}
    for side in ('local','visitante','total'):
        lines=np.array([m['linea'] for m in markets if m['kind']=='ou' and m['lado']==side])
        if not len(lines):continue
        if side!='total' or alpha<1e-8:
            dist=distributions[side]
            lo=dist.cdf(np.ceil(lines)-1);hi=dist.sf(np.floor(lines))
            mid=np.where(lines%1==0,dist.pmf(lines),0.)
            if side=='total':
                lo+=correccion_cdf(np.ceil(lines)-1,c);hi-=correccion_cdf(np.floor(lines),c)
                mid+=np.where(lines%1==0,np.where(lines==0,-c,np.where(lines==1,2*c,np.where(lines==2,-c,0.))),0.)
            ps=np.column_stack([lo,mid,hi])
        else:
            indices=np.arange(len(total))
            ps=np.array([[total[indices<line].sum(),total[indices==line].sum(),total[indices>line].sum()] for line in lines])
        ou.update({(side,line):p for line,p in zip(lines,ps)})
    rows=[]
    for market in markets:
        kind,side,line=market['kind'],market['lado'],market['linea']
        if kind=='1x2': p=np.array([away,draw,home])
        elif kind=='btts': p=np.array([1-btts,0.,btts])
        else: p=ou[(side,line)]
        if not np.isfinite(p).all() or min(p)<-1e-14 or abs(p.sum()-1)>2*TOL_COLA:
            raise ValueError('Vector experimental inválido')
        p=np.maximum(p,0);p/=p.sum()
        rows.append({**{a:b for a,b in market.items() if a!='regla'},
                     'p0':p[0],'p1':p[1],'p2':p[2],'y':observado(market,x,y)})
    logp=float(dl.logpmf(x)+dv.logpmf(y))
    if rho: logp+=np.log(mo.tau(x,y,ll,lv,rho))
    diag={'lambda_local':ll,'lambda_visitante':lv,'var_local':ll+alpha*ll*ll,
          'var_visitante':lv+alpha*lv*lv,'covarianza':-c,'nll_conjunta':-logp,
          'alpha':alpha,'rho':rho,'k_max':k,'masa_excluida':float(dl.sf(k)+dv.sf(k)-dl.sf(k)*dv.sf(k)),
          'real_local':x,'real_visitante':y,'fuera_soporte':x>k or y>k}
    for side,pmf,value in [('local',pl,x),('visitante',pv,y),('total',total,x+y)]:
        for q in (95,99):
            threshold=int(np.searchsorted(np.cumsum(pmf),q/100))
            diag[f'extremo_{side}_{q}']=value>threshold
            diag[f'p_extremo_{side}_{q}']=float(pmf[threshold+1:].sum())
    return rows,diag

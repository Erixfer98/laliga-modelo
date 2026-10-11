"""Medias positivas con exposición histórica; no altera modelo.K_ENCOGE."""
from dataclasses import dataclass, asdict
from itertools import product
import numpy as np
import modelo as mo


@dataclass(frozen=True)
class Config:
    kappa: float
    xi: float = .005
    ventana: int = 0
    rho: float = 0.
    familia: str = 'componentes'

    @property
    def id(self):
        return f'{self.familia}_k{self.kappa:g}_x{self.xi:g}_w{self.ventana}_r{self.rho:g}'

    def dict(self):
        return asdict(self)


def rejilla(metrica):
    configs = [Config(k, x, w) for k, x, w in product((1.,3.,10.,20.), (0.,.005,.01), (0,180))]
    if metrica in ('goles','goles_1t'):
        configs += [Config(c.kappa,c.xi,c.ventana,-.05) for c in configs]
    configs += [Config(k, familia='directa') for k in (3.,10.)]
    return configs


def resumen_historial(hist, fecha, metrica, xi, ventana=0):
    if not np.isfinite(xi) or xi < 0 or ventana < 0:
        raise ValueError('Recencia inválida')
    if (hist.fecha >= fecha).any():
        raise ValueError('Historial futuro o de la misma fecha')
    d = hist if not ventana else hist[hist.fecha >= fecha - __import__('pandas').Timedelta(days=ventana)]
    cl, cv, _ = mo.METRICAS[metrica]
    w = np.exp(-xi * (fecha-d.fecha).dt.days.to_numpy())
    x,y = d[cl].to_numpy(float),d[cv].to_numpy(float)
    # Gamma(0.5, 0.5): prior propio débil, declarado, común a métricas.
    # Pesos temporales son exposición fraccionaria; no se infiere cobertura posterior.
    ml = (np.dot(w,x)+.5)/(w.sum()+.5)
    mv = (np.dot(w,y)+.5)/(w.sum()+.5)
    def groups(col):
        names, idx = np.unique(d[col].to_numpy(str),return_inverse=True)
        e=np.bincount(idx,weights=w,minlength=len(names))
        sx=np.bincount(idx,weights=w*x,minlength=len(names))
        sy=np.bincount(idx,weights=w*y,minlength=len(names))
        return {name:(float(a),float(b),float(c)) for name,a,b,c in zip(names,e,sx,sy)}
    return ml,mv,groups('equipo_local_txt'),groups('equipo_visitante_txt')


def estimar(summary, local, visitante, config, actual=None):
    if not np.isfinite(config.kappa) or config.kappa <= 0:
        raise ValueError('El candidato requiere kappa positiva')
    ml,mv,casa,fuera=summary
    ec,scl,scv=casa.get(local,(0.,0.,0.)); ef,sfl,sfv=fuera.get(visitante,(0.,0.,0.))
    k=config.kappa
    if config.familia=='componentes':
        ll=((scl+k*ml)/(ec+k))*((sfl+k*ml)/(ef+k))/ml
        lv=((sfv+k*mv)/(ef+k))*((scv+k*mv)/(ec+k))/mv
    elif config.familia=='directa':
        base=(ml,mv) if actual is None else actual
        e=min(ec,ef)
        ll=(e*base[0]+k*ml)/(e+k);lv=(e*base[1]+k*mv)/(e+k)
    else:
        raise ValueError('Familia desconocida')
    if not np.isfinite([ll,lv]).all() or min(ll,lv)<=0:
        raise ValueError('Lambda experimental no positiva')
    return float(ll),float(lv)

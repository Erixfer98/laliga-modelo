"""Registro ex ante: rejilla fija y líneas por defecto de la app, sin cuotas ficticias."""
import numpy as np
import kuota as ku
import probabilidades as pr

# Se declara antes de examinar scores. Enteras comprueban pushes.
FIJAS = {
    'goles': ((.5,1.,1.5,2.,2.5,3.,3.5,4.5),(.5,1.,1.5,2.,2.5,3.5)),
    'goles_1t': ((.5,1.,1.5,2.,2.5),(.5,1.,1.5,2.5)),
    'goles_2t': ((.5,1.,1.5,2.,2.5),(.5,1.,1.5,2.5)),
    'tiros': ((10.5,15.5,20.,20.5,25.,25.5,30.,30.5,35.5,40.5),(5.5,10.,10.5,15.,15.5,20.5)),
    'tiros_a_puerta': ((3.5,5.,5.5,7.,7.5,9.,9.5,11.5,13.5),(.5,1.5,2.,2.5,3.5,4.,4.5,5.5,7.5)),
    'amarillas': ((1.5,2.5,3.,3.5,4.,4.5,5.,5.5,6.5),(.5,1.,1.5,2.,2.5,3.5)),
    'corners': ((5.5,7.,7.5,9.,9.5,11.,11.5,13.5),(.5,2.5,3.,3.5,4.5,5.,5.5,7.5)),
    'rojas': ((.5,1.,1.5),(.5,1.)),
}


def registro(met, ll, lv):
    cfg = ku.cfg_defecto(ll, lv, met, 'local', 'visitante')
    out = []
    for side in ('total', 'local', 'visitante'):
        default = set(ku.lineas(*cfg['Total' if side == 'total' else side]))
        fixed = set(FIJAS[met][0 if side == 'total' else 1])
        for line in sorted(default | fixed):
            if 0 <= line <= 100:
                out.append({'kind':'ou', 'lado':side, 'linea':float(line),
                            'fija':line in fixed, 'defecto':line in default,
                            'regla':{'tipo':'ou','lado':side,'linea':float(line),'over':True}})
    if met in ('goles','goles_1t','goles_2t'):
        out.extend([{'kind':'btts','lado':'total','linea':-1.,'fija':True,'defecto':True,
                     'regla':{'tipo':'btts','si':True}},
                    {'kind':'1x2','lado':'total','linea':-1.,'fija':True,'defecto':True,
                     'regla':{'tipo':'resultado','lado':'local'}}])
    return out


def probabilidades(m, markets):
    k = len(m)-1
    result = []
    for market in markets:
        win,push = pr.liquidacion(market['regla'],k)
        p2 = pr.prob_evento(m,win)
        if market['kind']=='1x2':
            draw,_ = pr.liquidacion({'tipo':'resultado','lado':'empate'},k)
            p1 = pr.prob_evento(m,draw)
        else:
            p1 = pr.prob_evento(m,push)
        excluded = draw if market['kind']=='1x2' else push
        p0 = pr.prob_evento(m,~(win|excluded))
        ps = np.array([p0,p1,p2])
        result.append(ps/ps.sum())
    return result


def observado(market, x, y):
    if market['kind']=='1x2':
        return 2 if x>y else (1 if x==y else 0)
    if market['kind']=='btts':
        return 2 if x>0 and y>0 else 0
    value = {'total':x+y,'local':x,'visitante':y}[market['lado']]
    return 2 if value>market['linea'] else (1 if value==market['linea'] else 0)

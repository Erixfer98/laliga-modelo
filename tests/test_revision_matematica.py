"""Oráculos analíticos independientes para la segunda revisión del PR."""
import math

import numpy as np
import pytest
from scipy.stats import poisson, skellam

import probabilidades as pr
import modelo as mo
import kuota as ku
from test_probabilidades import leg


@pytest.mark.parametrize('ll,lv,rho', [(0.,0.,-.05), (0.,2.,-.05), (1.2,2.7,-.05), (4.,3.,.03), (19.,.5,-.05)])
def test_dixon_coles_oraculos_analiticos(ll, lv, rho):
    m, meta = pr.distribucion(ll, lv, True, rho)
    k = meta['k_max']; z = poisson.cdf(k,ll)*poisson.cdf(k,lv)
    # DC redistribuye delta: -d,+d,+d,-d; cada marginal queda intacta.
    d = rho*ll*lv*math.exp(-ll-lv)
    assert m.sum(axis=1) == pytest.approx(poisson.pmf(np.arange(k+1),ll)/poisson.cdf(k,ll), abs=2e-15)
    assert m.sum(axis=0) == pytest.approx(poisson.pmf(np.arange(k+1),lv)/poisson.cdf(k,lv), abs=2e-15)
    # P(empate) independiente por serie de Bessel/Skellam; manejar lambda=0.
    draw = skellam.pmf(0,ll,lv) if ll and lv else math.exp(-ll-lv)
    assert np.trace(m) == pytest.approx(draw-2*d, abs=2*pr.TOL_COLA)
    x,y=np.indices(m.shape)
    for t, correction in ((0,-d),(1,2*d),(2,-d),(3,0.)):
        assert m[x+y==t].sum() == pytest.approx((poisson.pmf(t,ll+lv)+correction)/z, abs=2e-15)


@pytest.mark.parametrize('pw,pu,odds', [(.4,.2,3.),(.2,.3,2.),(.8,.1,1.5),(1e-20,0.,1e30),(.5,.5,2.),(0.,1.,2.)])
def test_kelly_push_formula_cerrada(pw,pu,odds):
    pl=max(0.,1-pw-pu); b=odds-1
    expected=min(1-1e-10,max(0.,(pw-pl/b)/(pw+pl))) if pw+pl else 0.
    actual=pr.kelly({odds:pw,1.:pu,0.:pl})
    assert actual == pytest.approx(expected,rel=5e-15,abs=0.)
    if pw==1e-20: assert actual>0


def test_kelly_general_optimo_y_concavidad():
    rng=np.random.default_rng(1776)
    for _ in range(150):
        returns=np.r_[0.,1.,rng.uniform(1.01,20,3)]
        probs=rng.dirichlet(np.ones(5))
        dist=dict(zip(returns,probs)); f=pr.kelly(dist)
        # Primeras y segundas derivadas independientes; log es cóncavo.
        b=returns-1
        derivative=float(np.sum(probs*b/(1+f*b)))
        assert np.sum(-probs*b*b/(1+f*b)**2)<0
        if f==0: assert np.dot(probs,b)<=1e-14
        elif f<1-1e-10: assert abs(derivative)<1e-9
        else: assert derivative>=-1e-9
        objective=np.sum(probs*np.log1p(f*b))
        for other in (0.,f/2,min(1-1e-10,f*1.5),.5):
            assert objective>=np.sum(probs*np.log1p(other*b))-1e-14


@pytest.mark.parametrize('dist',[{}, {2.:1.1,0.:-.1}, {2.:.5}, {2.:float('nan')}, {float('inf'):1.}, {-1.:1.}])
def test_distribuciones_invalidas_rechazadas(dist):
    for operation in (pr.ev,pr.kelly,lambda d:pr.combinar([d])):
        with pytest.raises(ValueError): operation(dist)


@pytest.mark.parametrize('p,push',[(.4,.8),(1.,.01),(-.1,.2),(.5,float('nan'))])
def test_cuota_justa_rechaza_masa_imposible(p,push):
    with pytest.raises(ValueError): mo.cuota_justa(p,push)


def test_retornos_rechaza_zip_truncado_y_matriz_invalida():
    rule={'tipo':'resultado','lado':'local'}
    for matrix,rules,odds in ((np.ones((2,2)),[rule],[2.]), (np.ones((2,3))/6,[rule],[2.]),
                             (np.eye(2)/2,[rule],[]),(np.eye(2)/2,[rule],[float('inf')]),
                             (np.eye(2)/2,[rule],[1.])):
        with pytest.raises(ValueError): pr.retornos(matrix,rules,odds)


def test_compatibilidad_fuera_de_soporte_poisson():
    rules=[{'tipo':'ou','lado':s,'linea':100.,'over':True} for s in ('local','visitante')]
    rules.append({'tipo':'resultado','lado':'local'})
    assert pr.compatibilidad(rules,[2.,2.,2.])==(True,8.)  # testigo (102,101)


def test_pushes_pueden_pagar_sin_acierto_total():
    rules=[{'tipo':'ou','lado':'local','linea':1.,'over':True},
           {'tipo':'ou','lado':'local','linea':2.,'over':False}]
    assert pr.compatibilidad(rules,[3.,3.])==(False,3.)
    # X=1 paga el under, X=2 el over; no existe X entero entre 1 y 2.
    m=np.zeros((4,4));m[1,0]=.4;m[2,0]=.4;m[0,0]=.2
    dist,p=pr.retornos(m,rules,[3.,3.])
    assert p==0; assert dist==pytest.approx({3.:.8,0.:.2})
    assert pr.ev(dist)==pytest.approx(1.4)
    assert pr.kelly(dist)==pytest.approx(.7)
    rb=ku.resumen_boleto([leg(regla=r,cuota=3.) for r in rules])
    assert rb['prob']==0 and rb['estado']=='calculado' and rb['kelly'] is not None
    assert any('retornos parciales' in a for a in rb['advertencias'])


def test_combinada_independiente_con_push_oraculo_exhaustivo():
    a={0.:.2,1.:.3,2.:.5};b={0.:.3,1.:.2,3.:.5}
    expected={0.:.44,1.:.06,2.:.1,3.:.15,6.:.25}
    combined=pr.combinar([a,b])
    assert combined==pytest.approx(expected)
    assert pr.ev(combined)==pytest.approx((1+pr.ev(a))*(1+pr.ev(b))-1)


def test_limite_escenarios_push_no_inventa_kelly(monkeypatch):
    m=np.zeros((3,3));m[0,0]=.2;m[1,0]=.3;m[2,0]=.5
    model={'matriz':m,'lambda_local':1.,'lambda_visitante':0.,'distribucion':{},
           'rango':{'lam_l':[0.,2.],'lam_v':[0.,1.],'esquinas':{i:m for i in range(17)}}}
    monkeypatch.setattr(ku,'_modelo_boleto',lambda *args:model)
    rules={'tipo':'ou','lado':'local','linea':1.,'over':True}
    # 17^3=4913 supera el límite; EV central exacto aún se conserva.
    legs=[leg(local=team,regla=rules,cuota=3.) for team in ('A','B','C')]
    rb=ku.resumen_boleto(legs)
    assert rb['disponible'] and rb['ev']==pytest.approx(1.8**3-1)
    assert rb['push']==pytest.approx(.3**3)
    assert rb['kelly'] is rb['ev_lo'] is rb['ev_hi'] is None
    assert ku.stake_desde_resumen(rb,1000)['opciones']==[]


def test_general_kelly_microscopico_con_varios_pagos():
    dist={0.:1-2e-20,1e30:1e-20,2e30:1e-20}
    f=pr.kelly(dist)
    assert f>0
    derivative=math.fsum(p*(r-1)/(1+f*(r-1)) for r,p in dist.items())
    assert abs(derivative)<1e-12


@pytest.mark.parametrize('ll,lv,k',[(1e308,0.,None),(1.,1.,1.5),(1.,1.,-1),(1.,1.,257)])
def test_soporte_extremo_rechazado_sin_overflow(ll,lv,k):
    with pytest.raises(ValueError): pr.distribucion(ll,lv,k=k)


def test_grupo_solo_push_puede_acompanar_otro_partido():
    rules=[{'tipo':'ou','lado':'local','linea':1.,'over':over} for over in (True,False)]
    assert pr.compatibilidad(rules,[3.,3.])==(False,1.)
    legs=[leg(regla=r,cuota=3.) for r in rules]
    assert ku.resumen_boleto(legs)['estado']=='incompatible'
    legs.append(leg(liga='premier',local='Arsenal',visitante='Chelsea'))
    rb=ku.resumen_boleto(legs)
    assert rb['estado']=='calculado' and rb['kelly'] is not None
    assert any(v['retorno']>1 and v['prob']>0 for v in rb['liquidaciones'])

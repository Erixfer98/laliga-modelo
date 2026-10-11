"""Banco causal y selección interna OOS. El mes externo nunca selecciona su modelo."""
import numpy as np
import pandas as pd
from evaluacion.mercados import FIJAS, registro
from .lambdas import rejilla, resumen_historial, estimar
from .distribuciones import primaria, score_primario, ajustar_alpha, predecir

MIN_PARTIDOS=100
MIN_MESES=2
MESES_INTERNOS=3
NB_METRICAS=('tiros','tiros_a_puerta','corners','amarillas','rojas')


def banco_liga(datos, counts, metricas=None, max_fixtures=None):
    """Cada score interno es una predicción diaria walk-forward independiente."""
    current=counts[(counts.modelo=='actual') & counts.maduro].copy()
    if metricas: current=current[current.metrica.isin(metricas)]
    if max_fixtures:
        ids=current.sort_values('fecha').fixture_id.drop_duplicates().head(max_fixtures)
        current=current[current.fixture_id.isin(ids)]
    records=[]
    for date,today in current.groupby('fecha',sort=True):
        hist=datos[datos.fecha<date]
        for met,group in today.groupby('metrica',observed=True):
            configs=rejilla(met);cache={}
            for conf in configs:
                key=(conf.xi,conf.ventana)
                if key not in cache: cache[key]=resumen_historial(hist,date,met,*key)
            side=primaria(met);lines=FIJAS[met][1 if side!='total' else 0]
            for row in group.itertuples(index=False):
                means=[estimar(cache[(c.xi,c.ventana)],row.local,row.visitante,c,
                               (row.lambda_local,row.lambda_visitante)) for c in configs]
                ll,lv=np.array(means).T
                scores=score_primario(ll,lv,row.real_local,row.real_visitante,lines,side,
                                      np.array([c.rho for c in configs]))
                for c,a,b,bs in zip(configs,ll,lv,scores):
                    records.append({'fixture_id':row.fixture_id,'fecha':date,'liga':row.liga,'metrica':met,
                        'candidato':c.id,'lambda_local':a,'lambda_visitante':b,'rho':c.rho,
                        'real_local':row.real_local,'real_visitante':row.real_visitante,'brier_interno':bs})
    return pd.DataFrame(records)


def seleccionar(bank,min_partidos=MIN_PARTIDOS,min_meses=MIN_MESES):
    """Tres meses internos previos, embargo de un día, score macro por liga."""
    rows=[];skips=[]
    for met,g in bank.groupby('metrica',observed=True):
        configs={c.id:c for c in rejilla(met)}
        for month in sorted(pd.to_datetime(g.fecha).dt.to_period('M').unique()):
            cutoff=month.start_time-pd.Timedelta(days=1)
            start=(month-MESES_INTERNOS).start_time
            train=g[(g.fecha>=start)&(g.fecha<cutoff)].copy()
            n=train.fixture_id.nunique();months=pd.to_datetime(train.fecha).dt.to_period('M').nunique()
            meta={'metrica':met,'mes_externo':str(month),'cutoff_exclusivo':str(cutoff.date()),
                  'inicio_validacion':str(start.date()),'partidos_internos':n,'meses_internos':months}
            if n<min_partidos or months<min_meses:
                skips.append({**meta,'motivo':'validación interna insuficiente'});continue
            # Cada candidato tiene exactamente la misma cohorte interna.
            if train.duplicated(['fixture_id','candidato']).any(): raise ValueError('Banco duplicado')
            if (train.groupby('fixture_id').candidato.nunique()!=len(configs)).any():
                raise ValueError('Candidatos con cohortes internas distintas')
            if set(train.candidato)!=set(configs): raise ValueError('Rejilla interna distinta')
            scores=train.groupby(['candidato','liga'],observed=True).brier_interno.mean().groupby('candidato').mean()
            best=scores.sort_index().sort_values(kind='stable').index[0]
            selected=train[train.candidato==best]
            pearson=((selected.real_local-selected.lambda_local)**2/selected.lambda_local+
                     (selected.real_visitante-selected.lambda_visitante)**2/selected.lambda_visitante)/2
            residual=float(pearson.mean())
            positives=int(((selected.real_local>0).astype(int)+(selected.real_visitante>0).astype(int)).sum())
            eligible=met in NB_METRICAS and residual>1.2 and positives>=30
            rows.append({**meta,'candidato':best,'score_validacion':float(scores[best]),
                         'train_max_fecha':str(train.fecha.max().date()),'pearson_interno':residual,
                         'observaciones_positivas':positives,'nb_habilitada':eligible,
                         'config':configs[best].dict()})
    return rows,skips


def dispersion_nb(bank,selection):
    """Se llama después de persistir el diagnóstico Poisson; nunca mira el mes externo."""
    result=[]
    for fit in selection:
        train=bank[(bank.metrica==fit['metrica'])&(bank.candidato==fit['candidato'])&
                   (bank.fecha>=pd.Timestamp(fit['inicio_validacion']))&
                   (bank.fecha<pd.Timestamp(fit['cutoff_exclusivo']))]
        alpha=ajustar_alpha(train) if fit['nb_habilitada'] else 0.
        result.append({**fit,'alpha':alpha,'razon_nb':'dispersión interna >1.2 y >=30 positivos'
                       if fit['nb_habilitada'] else 'Poisson: diagnóstico interno insuficiente o sin exceso'})
    return result


def evaluar_seleccion(bank, counts, selection, incluir_nb=False):
    from evaluacion.comparabilidad import validar_temporal
    validate=counts[counts.modelo=='actual'].copy();validar_temporal(validate)
    metadata=validate.set_index(['fixture_id','metrica'])
    configs={met:{c.id:c for c in rejilla(met)} for met in bank.metrica.unique()}
    predictions=[];diagnostics=[]
    for fit in selection:
        month=pd.Period(fit['mes_externo'],'M')
        chosen=bank[(bank.metrica==fit['metrica'])&(bank.candidato==fit['candidato'])&
                    (bank.fecha.dt.to_period('M')==month)]
        if pd.Timestamp(fit['train_max_fecha'])>=pd.Timestamp(fit['cutoff_exclusivo']):
            raise ValueError('Selección con fuga temporal')
        conf=configs[fit['metrica']][fit['candidato']]
        for row in chosen.itertuples(index=False):
            original=metadata.loc[(row.fixture_id,row.metrica)]
            markets=[m for m in registro(row.metrica,original.lambda_local,original.lambda_visitante) if m['fija']]
            base={k:original[k] for k in ('fixture_id','fecha','train_max_fecha','liga','temporada','local',
                                          'visitante','metrica','maduro','maduro_efectivo') if k in original}
            # Index keys are not columns after set_index.
            base.update(fixture_id=row.fixture_id,metrica=row.metrica)
            variants=[('poisson_regularizado',conf.rho,0.),('regularizado_sin_dc',0.,0.)]
            if incluir_nb:
                alpha=fit['alpha']
                variants.append(('nb_condicional',0. if alpha else conf.rho,alpha))
            for model,rho,alpha in variants:
                ps,diag=predecir(row.lambda_local,row.lambda_visitante,markets,
                                row.real_local,row.real_visitante,rho,alpha)
                extra={'modelo':model,'candidato':conf.id,'seleccion_train_max':fit['train_max_fecha']}
                predictions.extend([{**base,**extra,**p} for p in ps])
                diagnostics.append({**base,**extra,**diag})
    return pd.DataFrame(predictions),pd.DataFrame(diagnostics)

"""Comparación externa exploratoria; no elige ganador a partir del mes evaluado."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import modelo as mo
from evaluacion.comparabilidad import cohorte, MERCADO
from evaluacion.metricas import puntuar, resumen, calibracion
from evaluacion.datos import sha256
from evaluacion.reportes import tabla
from .distribuciones import primaria

BASE=('actual','sin_dc','liga','movil_10')
CANDIDATOS=('poisson_regularizado','nb_condicional')
PRIMARIOS=('tiros','tiros_a_puerta','goles','goles_1t','goles_2t','amarillas','corners')


def holm(p):
    p=np.asarray(p,float);order=np.argsort(p);out=np.empty(len(p))
    out[order]=np.minimum(1,np.maximum.accumulate(p[order]*(len(p)-np.arange(len(p)))))
    return out


def intervalos(d,replicas=2000,seed=20261011,referencias=('actual','liga','movil_10'),familia_primaria=True):
    """Mejora=referencia−candidato; bloques semanales, media por partido antes de remuestrear."""
    rows=[]
    for (met,kind,side),g in d.groupby(['metrica','kind','lado'],observed=True):
        for candidate in CANDIDATOS:
            if candidate not in set(g.modelo):continue
            for ref in referencias:
                pair=g[g.modelo.isin([candidate,ref])]
                # El llamador ya validó toda la cohorte; aquí volvemos a exigir las claves exactas.
                pair,_=cohorte(pair,modelos=(candidate,ref))
                per=pair.groupby(['fixture_id','fecha','modelo'],observed=True)[['brier','logloss']].mean().unstack('modelo')
                dates=pd.to_datetime(per.index.get_level_values('fecha'))
                week=dates.to_period('W-SUN').astype(str)
                diff=(per['brier'][ref]-per['brier'][candidate]).to_numpy()
                blocks=pd.DataFrame({'week':week,'delta':diff}).groupby('week').agg(total=('delta','sum'),n=('delta','size'))
                rng=np.random.default_rng(seed)
                draws=rng.integers(0,len(blocks),(replicas,len(blocks)))
                vals=blocks.total.to_numpy()[draws].sum(axis=1)/blocks.n.to_numpy()[draws].sum(axis=1)
                lo,hi=np.quantile(vals,[.025,.975])
                fortnight=(dates-pd.Timestamp('2025-01-06')).days//14
                b14=pd.DataFrame({'bloque':fortnight,'delta':diff}).groupby('bloque').agg(total=('delta','sum'),n=('delta','size'))
                draw14=rng.integers(0,len(b14),(replicas,len(b14)))
                v14=b14.total.to_numpy()[draw14].sum(axis=1)/b14.n.to_numpy()[draw14].sum(axis=1)
                lo14,hi14=np.quantile(v14,[.025,.975])
                signs=rng.choice([-1.,1.],size=(replicas,len(blocks)))
                null=(signs*blocks.total.to_numpy()).sum(axis=1)/blocks.n.sum()
                p=(1+np.count_nonzero(np.abs(null)>=abs(diff.mean())))/(replicas+1)
                ldiff=(per['logloss'][ref]-per['logloss'][candidate]).to_numpy()
                ll_lo=ll_hi=np.nan
                if np.isfinite(ldiff).all():
                    lblocks=pd.DataFrame({'week':week,'delta':ldiff}).groupby('week').agg(total=('delta','sum'))
                    lvals=lblocks.total.to_numpy()[draws].sum(axis=1)/blocks.n.to_numpy()[draws].sum(axis=1)
                    ll_lo,ll_hi=np.quantile(lvals,[.025,.975])
                rows.append({'metrica':met,'kind':kind,'lado':side,'candidato':candidate,'referencia':ref,
                    'partidos':len(per),'bloques':len(blocks),'mejora_brier':diff.mean(),'ic95_lo':lo,'ic95_hi':hi,
                    'bloques_14d':len(b14),'ic95_14d_lo':lo14,'ic95_14d_hi':hi14,
                    'p_bloques':p,'mejora_logloss':ldiff.mean(),'logloss_ic95_lo':ll_lo,'logloss_ic95_hi':ll_hi,
                    'logloss_inferencia_finita':bool(np.isfinite(ldiff).all()),
                    'primario':familia_primaria and met in PRIMARIOS and kind=='ou' and side==primaria(met)})
    out=pd.DataFrame(rows);out['p_holm']=np.nan
    mask=out.primario
    out.loc[mask,'p_holm']=holm(out.loc[mask,'p_bloques'])
    return out


def diagnostico(counts):
    rows=[]
    for (met,model,league),g in counts.groupby(['metrica','modelo','liga'],observed=True):
        for side in ('local','visitante','total'):
            x=g.real_local+g.real_visitante if side=='total' else g[f'real_{side}']
            lam=g.lambda_local+g.lambda_visitante if side=='total' else g[f'lambda_{side}']
            var=g.var_local+g.var_visitante+2*g.covarianza if side=='total' else g[f'var_{side}']
            sq=np.square(x-lam)
            pearson=np.divide(sq,var,out=np.zeros(len(g)),where=var>0)
            pearson[(var==0)&(x>0)]=np.inf
            row={'metrica':met,'modelo':model,'liga':league,'lado':side,'partidos':len(g),
                 'media_real':x.mean(),'media_predicha':lam.mean(),'sesgo':(lam-x).mean(),
                 'mae':abs(lam-x).mean(),'rmse':np.sqrt(sq.mean()),'pearson_condicional':pearson.mean(),
                 'nll_conjunta':g.nll_conjunta.mean(),'ceros_conjuntos':int(np.isinf(g.nll_conjunta).sum()),
                 'alpha_media':g.alpha.mean(),'fuera_soporte':int(g.fuera_soporte.sum())}
            for q in (95,99):
                row[f'cola_{q}_real']=g[f'extremo_{side}_{q}'].mean()
                row[f'cola_{q}_pred']=g[f'p_extremo_{side}_{q}'].mean()
            rows.append(row)
    return pd.DataFrame(rows)


def primarios(d):
    return d[(d.kind=='ou') & (d.lado==d.metrica.map(primaria))]


def confianza(d):
    s=d[(d.kind=='btts')|((d.kind=='ou')&(d.linea%1==.5))].copy()
    s['p_pick']=np.maximum(s.p0,s.p2)
    s['hit']=np.where(s.p2>=s.p0,s.y==2,s.y==0)
    s=s[s.p_pick>=.8]
    return s.groupby(['metrica','modelo'],observed=True).agg(partidos=('fixture_id','nunique'),
        selecciones=('fixture_id','size'),p_media=('p_pick','mean'),frecuencia=('hit','mean')).reset_index().assign(gap=lambda r:r.frecuencia-r.p_media)


def comparacion_final(d,interval,cal):
    p=primarios(d);rows=[]
    for met,g in p.groupby('metrica',observed=True):
        for candidate in CANDIDATOS:
            if candidate not in set(g.modelo):continue
            current=g[g.modelo=='actual'];new=g[g.modelo==candidate]
            tests=interval[(interval.metrica==met)&(interval.candidato==candidate)&(interval.kind=='ou')&(interval.lado==primaria(met))]
            monthly=g.assign(mes=g.fecha.dt.to_period('M').astype(str)).groupby(['mes','modelo'],observed=True).brier.mean().unstack()
            leagues=g.groupby(['liga','modelo'],observed=True).brier.mean().unstack()
            stability=float((monthly[candidate]<monthly.actual).mean())
            league_stability=float((leagues[candidate]<leagues.actual).mean())
            sufficient=len(tests)==3 and tests.partidos.min()>=300 and tests.bloques.min()>=12
            favorable=sufficient and tests.p_holm.notna().all() and (tests.p_holm<=.05).all() and (tests.ic95_lo>0).all()
            ll_ok=new.logloss.mean()<=current.logloss.mean()
            evidence='exploratoria favorable' if favorable and ll_ok and stability>=.7 and league_stability>=2/3 else 'evidencia insuficiente'
            base_cal=cal[(cal.metrica==met)&(cal.modelo=='actual')&(cal.kind=='ou')&(cal.lado==primaria(met))]
            ece_actual=np.average(base_cal.gap.abs(),weights=base_cal.selecciones) if len(base_cal) else np.nan
            c=cal[(cal.metrica==met)&(cal.modelo==candidate)&(cal.kind=='ou')&(cal.lado==primaria(met))]
            ece=np.average(c.gap.abs(),weights=c.selecciones) if len(c) else np.nan
            rows.append({'mercado':f'{met} OU {primaria(met)}','metrica':met,'candidato':candidate,
                'partidos':new.fixture_id.nunique(),'brier_actual':current.brier.mean(),'brier_candidato':new.brier.mean(),
                'brier_liga':g[g.modelo=='liga'].brier.mean(),'brier_movil':g[g.modelo=='movil_10'].brier.mean(),
                'mejora_brier':current.brier.mean()-new.brier.mean(),
                'logloss_actual':current.logloss.mean(),'logloss_candidato':new.logloss.mean(),
                'logloss_liga':g[g.modelo=='liga'].logloss.mean(),'logloss_movil':g[g.modelo=='movil_10'].logloss.mean(),
                'mejora_logloss':current.logloss.mean()-new.logloss.mean(),'ece_actual':ece_actual,'ece_candidato':ece,
                'meses_mejor_actual':stability,'ligas_mejor_actual':league_stability,'evidencia':evidence,
                'evidencia_independiente':'pendiente; histórico ya examinado'})
    return pd.DataFrame(rows)


def figuras(out,d,cal,interval,diag):
    names=[]
    fig,axes=plt.subplots(2,4,figsize=(16,8))
    for ax,met in zip(axes.ravel(),sorted(d.metrica.unique())):
        for model in ('actual',*CANDIDATOS):
            g=cal[(cal.metrica==met)&(cal.modelo==model)&(cal.kind=='ou')&
                  (cal.lado==primaria(met))&(cal.evento=='Over')].sort_values('p_media')
            strong=g[g.partidos>=30];thin=g[g.partidos<30]
            ax.plot(strong.p_media,strong.frecuencia,'o-',label=model,markersize=3)
            ax.scatter(thin.p_media,thin.frecuencia,marker='x',color='gray',s=10)
        ax.plot([0,1],[0,1],'k--',linewidth=.6);ax.set_title(met);ax.grid(alpha=.2);ax.legend(fontsize=6)
    fig.suptitle('Calibración exploratoria: mercado primario; cruces N<30 partidos')
    fig.tight_layout();fig.savefig(out/'calibracion.png',dpi=140);plt.close(fig);names.append('calibracion.png')
    fig,ax=plt.subplots(figsize=(12,6))
    sub=interval[(interval.referencia=='actual')&(interval.kind=='ou')&(interval.lado==interval.metrica.map(primaria))].reset_index(drop=True)
    for i,row in sub.iterrows():
        ax.plot([row.ic95_lo,row.ic95_hi],[i,i],color='tab:blue');ax.scatter(row.mejora_brier,i,s=20)
    ax.set_yticks(np.arange(len(sub)),[f'{r.metrica}: {r.candidato}' for r in sub.itertuples()])
    ax.axvline(0,color='black',linestyle='--');ax.set_xlabel('Mejora Brier: actual − candidato; IC semanal descriptivo')
    fig.tight_layout();fig.savefig(out/'intervalos.png',dpi=140);plt.close(fig);names.append('intervalos.png')
    fig,axes=plt.subplots(1,2,figsize=(14,5))
    sub=diag[(diag.lado=='local')&diag.modelo.isin(['actual',*CANDIDATOS])]
    for model,g in sub.groupby('modelo'):
        a=g.groupby('metrica').pearson_condicional.mean();finite=np.isfinite(a)
        axes[0].plot(a.index[finite],a[finite],'o-',label=model)
        axes[1].scatter(g.cola_99_pred,g.cola_99_real,label=model,alpha=.5)
    axes[0].axhline(1,color='black',linestyle='--');axes[0].tick_params(axis='x',rotation=60)
    axes[0].set_ylabel('Pearson² medio local; medias descriptivas por liga')
    axes[1].plot([0,.12],[0,.12],'k--');axes[1].set_xlabel('Cola 99 predicha');axes[1].set_ylabel('Cola observada')
    for ax in axes:ax.legend(fontsize=7);ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(out/'residuos_colas.png',dpi=140);plt.close(fig);names.append('residuos_colas.png')
    fig,axes=plt.subplots(2,4,figsize=(16,8))
    p=primarios(d).copy();p['mes']=p.fecha.dt.to_period('M').astype(str)
    month=p.groupby(['metrica','mes','modelo'],observed=True).brier.mean().reset_index()
    for ax,met in zip(axes.ravel(),sorted(d.metrica.unique())):
        for model in ('actual','liga','movil_10',*CANDIDATOS):
            g=month[(month.metrica==met)&(month.modelo==model)].sort_values('mes')
            ax.plot(g.mes,g.brier,'o-',label=model,markersize=2)
        ax.set_title(met);ax.tick_params(axis='x',rotation=70);ax.legend(fontsize=5);ax.grid(alpha=.2)
    fig.suptitle('Brier externo mensual; configuración seleccionada solo en ventanas internas previas')
    fig.tight_layout();fig.savefig(out/'estabilidad.png',dpi=140);plt.close(fig);names.append('estabilidad.png')
    return names


def generar(out,pred,diag,counts,cache,meta,selection,skips,manifest):
    out=Path(out)
    name='predicciones.csv.gz'
    if sha256(cache/name)!=meta['artefactos_sha256'][name]: raise ValueError('Predicciones Fase 2 alteradas')
    raw=pd.read_csv(cache/name,parse_dates=['fecha','train_max_fecha'],float_precision='round_trip')
    keys=pred[MERCADO].drop_duplicates()
    baseline=raw[raw.maduro&raw.fija].merge(keys,on=MERCADO,how='inner',validate='many_to_one')
    models=(*BASE,*sorted(pred.modelo.unique()))
    common,audit=cohorte(pd.concat([baseline,pred],ignore_index=True),modelos=models)
    if len(common)!=len(baseline)+len(pred): raise ValueError('Cohorte externa incompleta: abortar, no ocultar fallos')
    d=puntuar(common);d['es_push']=(d.kind=='ou')&(d.y==1)
    count_keys=diag[['fixture_id','metrica']].drop_duplicates()
    legacy=counts.merge(count_keys,on=['fixture_id','metrica'],how='inner',validate='many_to_one')
    legacy['var_local']=legacy.lambda_local;legacy['var_visitante']=legacy.lambda_visitante
    legacy['covarianza']=np.where((legacy.modelo=='actual')&legacy.metrica.isin(['goles','goles_1t']),
        -mo.RHO*legacy.lambda_local*legacy.lambda_visitante*np.exp(-legacy.lambda_local-legacy.lambda_visitante),0.)
    legacy['alpha']=0.
    count_common,count_audit=cohorte(pd.concat([legacy,diag],ignore_index=True),modelos=models,keys=['fixture_id','metrica'])
    if len(count_common)!=len(legacy)+len(diag):raise ValueError('Conteos externos incompletos')
    interval=intervalos(d)
    cal=calibracion(d,['metrica','modelo','kind','lado'])
    diagnostic=diagnostico(count_common)
    final=comparacion_final(d,interval,cal)
    dc=d[d.metrica.isin(['goles','goles_1t'])&d.modelo.isin(['poisson_regularizado','regularizado_sin_dc'])].copy()
    dc['modelo']=dc.modelo.replace({'regularizado_sin_dc':'actual'})
    dc_intervals=intervalos(dc,referencias=('actual',),familia_primaria=False)
    dc_intervals['referencia']='regularizado_sin_dc'
    nb_intervals=pd.DataFrame()
    if 'nb_condicional' in set(d.modelo):
        nb=d[d.modelo.isin(['poisson_regularizado','nb_condicional'])].copy()
        nb['modelo']=nb.modelo.replace({'poisson_regularizado':'actual'})
        nb_intervals=intervalos(nb,referencias=('actual',),familia_primaria=False)
        nb_intervals['referencia']='poisson_regularizado'
    tables={'comparacion':resumen(d,['metrica','modelo']),
            'mercados':resumen(d,['metrica','kind','lado','modelo']),
            'ligas':resumen(d,['liga','metrica','kind','lado','modelo']),
            'lineas':resumen(d,['liga','metrica','kind','lado','linea','modelo']),
            'mensual':resumen(d.assign(mes=d.fecha.dt.to_period('M').astype(str)),['mes','metrica','kind','lado','modelo']),
            'calibracion':cal,'calibracion_ligas':calibracion(d,['liga','metrica','modelo','kind','lado']),
            'intervalos':interval,'conteos':diagnostic,'comparabilidad':audit,'comparabilidad_conteos':count_audit,
            'comparacion_primaria':final,'dixon_coles':dc_intervals,'nb_vs_poisson':nb_intervals,'confianza_80':confianza(d),
            'sensibilidad_efectivo':resumen(d[d.maduro_efectivo],['metrica','modelo'])}
    for name,frame in tables.items():frame.to_csv(out/f'{name}.csv',index=False,float_format='%.10g')
    figures=figuras(out,d,cal,interval,diagnostic)
    fits=pd.DataFrame([{k:v for k,v in s.items() if k!='config'} for s in selection])
    fits.to_csv(out/'selecciones.csv',index=False,float_format='%.10g')
    nb_count=int(fits.nb_habilitada.sum())
    coverage=d[d.modelo=='actual'].groupby('liga').agg(partidos=('fixture_id','nunique'),desde=('fecha','min'),hasta=('fecha','max')).reset_index()
    manifest.update(filas_externas=len(d),partidos_externos=int(d.fixture_id.nunique()),
                    cohortes_completas=True,selecciones=len(selection),nb_habilitada_cortes=nb_count,
                    familia_holm=int(interval.primario.sum()))
    report=f'''# Fase 3 — Regularización y dispersión experimental

## Dictamen

Se conserva el modelo vigente. Ningún candidato se activa en producción y no se modifica la interfaz
ni el motor de liquidación. Los resultados son **exploratorios retrospectivos**, no evidencia independiente
ni rentabilidad demostrada. El histórico ya fue examinado en Fase 2 y motivó estos experimentos.
Los candidatos de la tabla son estrategias seleccionadas internamente, no ganadores escogidos con los meses externos.

## Datos y cohortes

{sum(x['partidos'] for x in meta['datos'])} partidos históricos; {d.fixture_id.nunique()} partidos externos evaluables,
{len(d):,} filas entre {len(models)} modelos sobre exactamente las mismas claves y objetivos.
Se exige la cohorte madura y líneas fijas de Fase 2. Meses sin validación interna suficiente se omiten
para todos los comparadores y quedan en `seleccion_poisson.json`. Un fallo parcial de ejecución aborta
el informe en lugar de mejorar el score mediante exclusiones. La muestra es condicional al historial.

{tabla(coverage)}

No hay disponibilidad original certificada ni snapshots completos de revisiones históricas. Liga MX
requiere contraste adicional de definiciones. CSV y Excel no son muestras independientes.

## Protocolo temporal anidado

Cada lambda del banco se estima con datos de fechas anteriores al partido. Antes de cada mes externo,
se comparan scores de predicciones diarias OOS de los tres meses internos previos, excluyendo el día
anterior al inicio del mes. Se requieren >=100 partidos y >=2 meses internos. Se minimiza Brier primario
macro por liga y se desempata por ID declarado; nunca se utilizan objetivos externos para seleccionar.

Objetivo interno: OU local en tiros; OU total en tiros a puerta, goles/1T/2T, amarillas, córners y rojas.
La rejilla comprende kappa={{1,3,10,20}}, xi={{0,.005,.01}}, ventana={{todo,180 días}}. En goles y 1T se
compara rho={{0,-.05}}; se añaden dos controles de encogimiento directo. No se reajusta la rejilla al ver
los resultados. La selección es compartida entre ligas, pero cada media usa exclusivamente su liga histórica.

Las medias de liga usan prior Gamma(0.5,0.5), declarado, y cada componente recibe kappa exposiciones
hacia esa media positiva. Es regularización con exposición fraccionaria, no certificación de cobertura bayesiana.
El encogimiento directo usa el mínimo de exposiciones de ambos equipos y la lambda actual.
`regularizado_sin_dc` mantiene las lambdas seleccionadas y elimina DC como ablación controlada.

## Poisson antes de binomial negativa

El piloto se ejecutó antes del banco completo; sus resultados de coste están en `piloto.json`.
Se persistieron selección y residuos Poisson en `seleccion_poisson.json` y `poisson_previo.json` antes de estimar NB.
Solo se habilita NB en un corte para tiros/tiros a puerta/córners/amarillas/rojas cuando el residuo Pearson
medio **interno OOS** supera 1.2 y hay >=30 observaciones positivas. Nunca se usa la dispersión del mes
externo para habilitarlo. Hay {nb_count} cortes habilitados de {len(selection)} selecciones.

NB2 conserva las medias Poisson seleccionadas y estima alpha en [0,2] por likelihood de los conteos
internos OOS. Su varianza es lambda+alpha×lambda². Si no cumple el diagnóstico o no mejora la likelihood
interna frente a alpha=0, vuelve a Poisson; `nb_condicional` denota esa estrategia causal, no NB en todos
los partidos. Se comparten alpha por métrica/corte; sus diferencias por liga se diagnostican por separado.
No se combina NB con la corrección DC diseñada para Poisson. `nb_vs_poisson.csv` mide el efecto
incremental de cambiar la distribución sobre las mismas lambdas seleccionadas, con IC por bloques;
es diagnóstico, no un mecanismo para seleccionar ganadores externos.

## Comparación por mercado primario

Mejora positiva favorece al candidato. No se elige retrospectivamente el mejor entre Poisson y NB.
Se presentan ambos y se conservan las referencias de liga y móvil.

{tabla(final[['mercado','candidato','partidos','brier_actual','brier_candidato','brier_liga','brier_movil','mejora_brier','logloss_actual','logloss_candidato','mejora_logloss','evidencia']])}

Log Loss estricto conserva infinito cuando el observado tenía probabilidad cero. Los intervalos de
Log Loss solo se calculan cuando **todas** las diferencias son finitas; no se eliminan filas infinitas
para obtener una comparación favorable. El diagnóstico recortado es separado y no decide la selección.

## Incertidumbre, multiplicidad y estabilidad

Se promedian líneas por partido y se remuestrean semanas completas con 2.000 réplicas y semilla fija.
Las columnas IC95 son descriptivas; se añade sensibilidad con bloques de 14 días (`ic95_14d_*`). El contraste bilateral de diferencias usa cambios de signo por
bloque semanal; Holm ajusta una familia de {int(interval.primario.sum())} contrastes primarios (mercados,
estrategias y referencias actual/liga/móvil). Los diagnósticos por línea, liga, BTTS y 1X2 no son
confirmatorios. La independencia aproximada de semanas no elimina toda dependencia entre equipos.

Etiqueta exploratoria favorable exige >=300 partidos, >=12 semanas, IC favorable y p Holm<=.05 frente
a las tres referencias, sin empeorar Log Loss frente al actual, mejora en >=70% de meses y >=2/3 de ligas.
Es una regla descriptiva predefinida, no permiso para instalar un modelo. El resto es evidencia insuficiente.
Las tablas por liga/mes incluyen tamaño de muestra; no convierten varias líneas en partidos independientes.

{tabla(interval[(interval.referencia=='actual')&(interval.kind=='ou')&(interval.lado==interval.metrica.map(primaria))][['metrica','candidato','partidos','bloques','mejora_brier','ic95_lo','ic95_hi','p_holm','logloss_ic95_lo','logloss_ic95_hi']])}

## Likelihood, residuos, calibración y colas

`conteos.csv` presenta likelihood conjunta no truncada, sesgo, RMSE, Pearson² y colas 95/99 por liga,
modelo y lado. Para total se utiliza la suma de varianzas y la covarianza DC; NB mantiene independencia.
Las probabilidades OU Poisson marginales/totales son analíticas. NB total usa convolución con cola
excluida <=1e-12; se registran soporte y observaciones fuera de él. Las medias positivas evitan ceros
estructurales de los candidatos; no se fuerza epsilon para ocultar limitaciones del modelo actual.

`calibracion*.csv` contiene bins one-vs-rest, incluidos pushes. ECE y Wilson son descriptivos por selecciones
correlacionadas, no inferencia independiente. `confianza_80.csv` muestra sobreconfianza de lados favoritos.
No se instala ni se selecciona un calibrador nuevo. `dixon_coles.csv` compara las mismas lambdas
seleccionadas con su rho interno frente a rho=0; sus intervalos son diagnósticos y no forman parte
de la familia confirmatoria. Valores infinitos de Pearson no se dibujan, pero se conservan en CSV.

## Evidencia independiente y registro prospectivo

La evaluación independiente permanece **pendiente**. Julio–septiembre de 2026 ya se examinó en Fase 2:
no puede presentarse como holdout inédito. Tras congelar código/configuración, se deben registrar
predicciones antes del kickoff para partidos futuros; no se cambiarán hiperparámetros usando ese período.

`experimentos.registro` ofrece CLI opt-in y SQLite append-only con ID idempotente, timestamps UTC,
commit, modelo, lambdas, probabilidades y hashes de archivos realmente suministrados. Rechaza datos
posteriores a la generación y registros después del kickoff. La cadena detecta alteraciones ordinarias;
no sustituye firmas externas ni certifica timestamps declarados por el proveedor. No se conecta a producción.
No se han capturado predicciones reales futuras ni cuotas como parte de este backtesting.

## Figuras

{chr(10).join(f'![{name}]({name})' for name in figures)}

## Reproducción

```bash
python -m experimentos --piloto
python -m experimentos --etapa poisson --procesos 2
python -m experimentos --etapa nb --procesos 2
python -m pytest -q
```

Se necesita el caché verificable Fase 2: `python -m evaluacion --guardar-predicciones --procesos 2` si no
está disponible. Los bancos gzip son regenerables y no se versionan; parámetros, informes y hashes sí.
No se inventan cuotas ni se calculan ROI, CLV o rentabilidad. Producción conserva el modelo vigente.
'''
    (out/'REPORTE.md').write_text(report)

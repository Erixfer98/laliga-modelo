"""Artefactos auditables y gráficos estáticos, sin interfaz de producción."""
from pathlib import Path
import json

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from .comparabilidad import cohorte
from .metricas import resumen, calibracion, bootstrap_pareado, bootstrap_mercados


def tabla(df, cols=None, decimals=4):
    if cols is not None: df=df[cols]
    headers=[str(c) for c in df.columns]
    lines=['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']
    for row in df.itertuples(index=False,name=None):
        vals=[]
        for v in row:
            if isinstance(v,(float,np.floating)):
                v='∞' if np.isinf(v) else ('—' if pd.isna(v) else f'{v:.{decimals}f}')
            vals.append(str(v).replace('|','/'))
        lines.append('| '+' | '.join(vals)+' |')
    return '\n'.join(lines)


def confianza_alta(d):
    s=d[(d.modelo=='actual')&((d.kind=='btts')|((d.kind=='ou')&(d.linea%1==.5)))].copy()
    s['p_pick']=np.maximum(s.p0,s.p2)
    s['hit']=np.where(s.p2>=s.p0,s.y==2,s.y==0).astype(int)
    s=s[s.p_pick>=.8]
    return s.groupby(['metrica'],observed=True).agg(partidos=('fixture_id','nunique'),
        selecciones=('p_pick','size'),p_media=('p_pick','mean'),frecuencia=('hit','mean'))\
        .reset_index().assign(gap=lambda r:r.frecuencia-r.p_media)


def ranking(d, cal):
    rows=[]
    for (met,kind,side),g in d.groupby(['metrica','kind','lado'],observed=True):
        current=g[g.modelo=='actual'];league=g[g.modelo=='liga'];moving=g[g.modelo=='movil_10']
        n=current.fixture_id.nunique()
        month=g.assign(mes=pd.to_datetime(g.fecha).dt.to_period('M')).groupby(['mes','modelo'],observed=True).brier.mean().unstack()
        stable=float((month.actual<month.liga).mean())
        c=cal[(cal.modelo=='actual')&(cal.metrica==met)&(cal.kind==kind)&(cal.lado==side)]
        ece=np.average(c.gap.abs(),weights=c.selecciones) if len(c) else np.nan
        classes=(0,2) if kind=='btts' else (0,1,2)
        minor=min(current.loc[current.y==cls,'fixture_id'].nunique() for cls in classes)
        eligible=n>=300 and len(month)>=3 and minor>=20
        skill=1-current.brier.mean()/league.brier.mean() if league.brier.mean()>0 else np.nan
        rows.append({'metrica':met,'kind':kind,'lado':side,'partidos':n,'selecciones':len(current),
                     'brier_actual':current.brier.mean(),'brier_liga':league.brier.mean(),
                     'brier_movil':moving.brier.mean(),'skill_vs_liga':skill,'ece':ece,
                     'meses':len(month),'fraccion_meses_mejor_liga':stable,
                     'ceros_observados':int(current.cero_observado.sum()),
                     'evidencia':'exploratoria' if eligible else 'insuficiente',
                     'potencial_economico':'pendiente de cuotas verificables'})
    r=pd.DataFrame(rows)
    # Orden descriptivo multcriterio; no combina escalas arbitrarias en un score.
    r=r.sort_values(['evidencia','skill_vs_liga','ece','fraccion_meses_mejor_liga','partidos'],
                    ascending=[True,False,True,False,False]).reset_index(drop=True)
    r.insert(0,'orden_descriptivo',np.arange(1,len(r)+1))
    return r


def graficas(out,d,cal,comparison,counts,monthly):
    out=Path(out);names=[]
    fig,axes=plt.subplots(2,4,figsize=(16,8),sharex=True,sharey=True)
    for ax,(met,g) in zip(axes.ravel(),cal[cal.modelo=='actual'].groupby('metrica',observed=True)):
        for side,c in g[(g.kind=='ou')&(g.evento=='Over')].groupby('lado',observed=True):
            c=c.sort_values('p_media')
            stable=c[c.partidos>=30];thin=c[c.partidos<30]
            ax.plot(stable.p_media,stable.frecuencia,'o-',label=side,markersize=3)
            ax.scatter(thin.p_media,thin.frecuencia,color='gray',marker='x',s=15,alpha=.6)
        ax.plot([0,1],[0,1],'k--',linewidth=.8);ax.set_title(met);ax.grid(alpha=.2)
        ax.set_xlabel('Probabilidad predicha');ax.set_ylabel('Frecuencia observada');ax.legend(fontsize=7)
    fig.suptitle('Calibración descriptiva: líneas fijas; curvas N≥30 partidos, cruces grises N<30')
    fig.tight_layout();fig.savefig(out/'calibracion.png',dpi=140);plt.close(fig);names.append('calibracion.png')
    fig,ax=plt.subplots(figsize=(12,5))
    comparison.pivot(index='metrica',columns='modelo',values='brier').plot.bar(ax=ax)
    ax.set_ylabel('Brier normalizado (menor es mejor)');ax.set_title('Comparación emparejada por métrica');ax.grid(axis='y',alpha=.2)
    fig.tight_layout();fig.savefig(out/'comparacion.png',dpi=140);plt.close(fig);names.append('comparacion.png')
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    c=counts[(counts.modelo=='actual')&(counts.lado=='local')]
    for met,g in c.groupby('metrica',observed=True):
        finite=np.isfinite(g.pearson_condicional)
        if finite.any(): axes[0].scatter([met]*finite.sum(),g.loc[finite,'pearson_condicional'],alpha=.7,s=20)
    axes[0].axhline(1,color='black',linestyle='--');axes[0].tick_params(axis='x',rotation=65)
    axes[0].set_ylabel('Media del residuo de Pearson²');axes[0].set_title('Dispersión condicional por liga (local)')
    for met,g in c.groupby('metrica',observed=True):
        axes[1].scatter(g.cola_99_pred,g.cola_99_real,label=met,s=25)
    maxlim=max(float(c.cola_99_real.max()),.04)*1.1
    axes[1].plot([0,maxlim],[0,maxlim],'k--');axes[1].set_xlabel('Cola > cuantil 99: predicha')
    axes[1].set_ylabel('Cola observada');axes[1].legend(fontsize=7);axes[1].set_title('Extremos; umbral discreto específico del partido')
    fig.tight_layout();fig.savefig(out/'errores_colas.png',dpi=140);plt.close(fig);names.append('errores_colas.png')
    fig,axes=plt.subplots(2,4,figsize=(16,8))
    for ax,(met,g) in zip(axes.ravel(),monthly.groupby('metrica',observed=True)):
        for model in ('actual','liga','movil_10'):
            s=g[g.modelo==model].sort_values('mes');ax.plot(s.mes,s.brier,'o-',label=model,markersize=3)
        ax.set_title(met);ax.tick_params(axis='x',rotation=70);ax.grid(alpha=.2);ax.legend(fontsize=6)
    fig.suptitle('Estabilidad temporal; Brier sobre líneas fijas')
    fig.tight_layout();fig.savefig(out/'estabilidad.png',dpi=140);plt.close(fig);names.append('estabilidad.png')
    return names


def generar(out,scored,counts,abst,inventory,manifest,calibrated,fits,skips):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    d=scored[scored.maduro&scored.fija].copy()
    d['es_push']=(d.kind=='ou')&(d.y==1)
    comparison=resumen(d,['metrica','modelo'])
    segments=resumen(d,['liga','metrica','kind','lado','linea','modelo'])
    cal=calibracion(d,['metrica','modelo','kind','lado'])
    leaguecal=calibracion(d,['liga','metrica','modelo','kind','lado'])
    linescal=calibracion(d,['liga','metrica','modelo','kind','lado','linea'])
    monthly=resumen(d.assign(mes=d.fecha.dt.to_period('M').astype(str)),['mes','metrica','modelo'])
    paired=bootstrap_pareado(d)
    ranks=ranking(d,cal)
    market_boot=bootstrap_mercados(d)
    intervals=market_boot[market_boot.referencia=='liga'][['metrica','kind','lado','ic95_lo','ic95_hi']]
    ranks=ranks.merge(intervals,on=['metrica','kind','lado'],how='left')
    high=confianza_alta(d)
    effective=resumen(d[d.maduro_efectivo],['metrica','modelo'])
    from .metricas import diagnostico_conteos, puntuar
    diagnostic=diagnostico_conteos(counts)
    tables={'comparacion':comparison,'segmentos':segments,'calibracion':cal,'calibracion_ligas':leaguecal,
            'calibracion_lineas':linescal,'bootstrap_mercados':market_boot,'mensual':monthly,'bootstrap':paired,'ranking':ranks,
            'confianza_80':high,'sensibilidad_n_efectivo':effective,'conteos':diagnostic,'abstenciones':abst}
    experiment=pd.DataFrame();holdout=pd.DataFrame()
    if not calibrated.empty:
        keys=['fixture_id','metrica','kind','lado','linea']
        base=scored[scored.modelo=='actual'].merge(calibrated[keys].drop_duplicates(),on=keys,how='inner')
        experiments, experiment_audit = cohorte(
            pd.concat([base,puntuar(calibrated)],ignore_index=True),
            modelos=('actual','platt','isotonica'))
        tables['comparabilidad_calibradores']=experiment_audit
        experiment=resumen(experiments,['metrica','modelo'])
        holdout=resumen(experiments[experiments.fecha>=pd.Timestamp(manifest['holdout_desde'])],['metrica','modelo'])
        tables['calibradores']=experiment;tables['calibradores_holdout']=holdout
        tables['calibradores_mensual']=resumen(experiments.assign(mes=experiments.fecha.dt.to_period('M').astype(str)),['mes','metrica','modelo'])
        tables['calibradores_ligas']=resumen(experiments,['liga','metrica','modelo'])
        tables['calibradores_bootstrap']=bootstrap_pareado(experiments,referencias=('platt','isotonica'))
        final=experiments[experiments.fecha>=pd.Timestamp(manifest['holdout_desde'])]
        if len(final):
            tables['calibradores_bootstrap_holdout']=bootstrap_pareado(final,referencias=('platt','isotonica'))
    for name,frame in tables.items():frame.to_csv(out/f'{name}.csv',index=False,float_format='%.10g')
    names=graficas(out,d,cal,comparison,diagnostic,monthly)
    (out/'calibradores.json').write_text(json.dumps({'ajustes':fits,'omitidos':skips},ensure_ascii=False,indent=2)+'\n')
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    inv=pd.DataFrame(inventory)[['liga','partidos','desde','hasta']]
    countcurrent=counts[counts.modelo=='actual']
    coverage=countcurrent.groupby('liga',observed=True).agg(predicciones_conteo=('fixture_id','size'),partidos=('fixture_id','nunique'),maduro=('maduro','sum')).reset_index()
    # Cada partido aparece una vez por métrica: dividir no es estimar independencia.
    coverage['partidos_maduros']=countcurrent[countcurrent.maduro].groupby('liga').fixture_id.nunique().reindex(coverage.liga).to_numpy()
    current=comparison[comparison.modelo=='actual']; refs=paired[paired.referencia=='liga']
    improvements=refs[refs.ic95_hi<0].metrica.tolist();worse=refs[refs.ic95_lo>0].metrica.tolist()
    countissues=diagnostic[(diagnostic.modelo=='actual')&(diagnostic.lado=='local')]
    report=f'''# Fase 2: validación histórica y calibración

## Resumen ejecutivo

Evaluación retrospectiva del algoritmo actual sobre {sum(x['partidos'] for x in inventory)} partidos de seis ligas.
El entrenamiento excluye encuentros de la fecha evaluada y fechas posteriores. No se puede certificar
la disponibilidad original de cada estadística ni reproducir predicciones publicadas: no existen snapshots completos as-of.
No se modifica el modelo ni se activa calibración en producción.

En la muestra madura, líneas fijas y comparación emparejada, las diferencias de Brier frente a la
referencia de liga tienen IC descriptivo semanal completamente favorable para: **{', '.join(improvements) or 'ninguna métrica'}**;
y desfavorable para: **{', '.join(worse) or 'ninguna métrica'}**.
Los intervalos no están corregidos por múltiples comparaciones y no certifican generalización.
Un ranking predictivo no demuestra rentabilidad: no hay cuotas históricas verificables.

## Datos y cobertura

{tabla(inv)}

{tabla(coverage[['liga','partidos','partidos_maduros']])}

Datos completos para las métricas solicitadas. CSV y Excel son copias, no muestras adicionales.
Fuentes: football-data para Europa y ESPN para Liga MX. No se ha contrastado cada valor con la fuente.
Liga MX carece de metadatos que permitan certificar tiempo reglamentario y definición de tarjetas.
Sus resultados son diagnósticos, sujetos a esa reserva. No se imputan faltantes; datos corruptos detienen la ejecución.

## Metodología y prevención de fuga

- Corte por fecha de fuente, no por jornada estimada. Todos los encuentros del mismo día se excluyen del historial.
- XI={manifest['parametros']['XI']}, rho={manifest['parametros']['RHO']}, K_ENCOGE={manifest['parametros']['K_ENCOGE']}, sin ajustes.
- El modelo actual utiliza `modelo.fuerzas`, `modelo.lambdas` y `probabilidades.distribucion` de Fase 1.
- Se validan nombres de modelos, unicidad, objetivos y metadatos comunes. Las cohortes incompletas
  se excluyen para todos los modelos y se auditan en `comparabilidad_*.csv`, incluidos conteos y calibradores.
- La selección sigue siendo condicional al historial disponible; excluir abstenciones no demuestra ausencia
  de sesgo respecto a partidos sin historial. Los datos corruptos detienen la ejecución.
- Las cuatro referencias comparten partidos y líneas; no se sustituyen equipos desconocidos dentro del modelo actual.
- Liga: medias históricas con pesos XI; móvil: últimos diez encuentros del equipo en la condición, sin ajuste por rival.
- Sin DC: mismas lambdas actuales, eliminando únicamente la corrección de las cuatro celdas de baja anotación.
- `fija` es una rejilla declarada en código antes de medir resultados. `defecto` reproduce configuración de la app;
  ambas banderas se registran. Tablas principales usan `fija`; las predicciones guardan también `defecto`.
- Muestra principal: ambos equipos con >=5 encuentros previos en la condición. Sensibilidad adicional exige n efectivo >=5.
- Partidos sin datos suficientes no se borran del registro; abstenciones y cobertura se exportan por separado.
- Las estadísticas de segundo tiempo del propio encuentro solo forman parte del objetivo observado.
- La calificación 0.6×probabilidad+0.4×historial de la app no se considera una probabilidad calibrada.

Brier se normaliza como ½Σ(p_k−y_k)²: coincide con Brier binario convencional y va de 0 a 1.
OU entero usa clases Under/Push/Over; BTTS usa No/Sí; 1X2 usa Visitante/Empate/Local.
Un empate de 1X2 no es devolución. Las curvas one-vs-rest incluyen la clase Push explícitamente.
Log Loss estricto es infinito si la clase observada tenía probabilidad cero. `logloss_clip` usa epsilon=1e-15
solo como diagnóstico finito; las tablas conservan ceros estructurales y el score estricto.
No se inventan cuotas ni se simula rentabilidad.

Las comparaciones bootstrap promedian líneas dentro del partido, emparejan modelos y remuestrean semanas
(1.000 réplicas, semilla fija). No cuentan cada línea como partido independiente. Wilson en curvas es
una referencia descriptiva por bin, no inferencia robusta ante correlación entre líneas o equipos.

## Comparación probabilística

{tabla(comparison[['metrica','modelo','partidos','brier','logloss','ceros_observados']])}

Deltas negativos favorecen al modelo actual. Referencia de liga:

{tabla(refs)}

Otras comparaciones, ligas, líneas, lados y meses: archivos CSV de este directorio.
No compare directamente Brier de eventos muy raros con mercados equilibrados: use habilidad frente a referencia.

## Probabilidades superiores al 80%

Se toma el lado más probable entre Over/Under o Sí/No, exclusivamente para medias líneas y BTTS.
Estas selecciones están correlacionadas; se muestran también partidos únicos. Gap negativo indica sobreconfianza.

{tabla(high)}

## Distribuciones, errores y extremos

La likelihood conjunta usa el proceso Poisson/DC no truncado en logaritmos, evitando underflow de PMF;
las probabilidades de mercados usan el soporte condicionado de Fase 1 (cola <=1e-12).
Se registra cada observación fuera del soporte y cada probabilidad estructuralmente cero.
La dispersión condicional se estima con (observado−lambda)²/varianza predictiva; valores >1 sugieren
variación no explicada, pero también pueden reflejar errores en medias o incertidumbre de estimación.
No basta para concluir que binomial negativa será mejor. Para total con DC se incluye su cambio de varianza.
Las colas comparan excedencia del cuantil específico 95/99 de cada partido con su probabilidad exacta
(discreta, que no tiene por qué ser 5%/1%).

Diagnóstico local por liga del modelo actual:

{tabla(countissues[['metrica','liga','partidos','mae','pearson_condicional','cola_99_real','cola_99_pred','ceros_estructurales_conjuntos']])}

## Calibración experimental temporal

Mapas Platt monótonos e isotónica PAVA, compartidos por métrica/lado/tipo entre ligas,
solo para medias líneas y BTTS. Se entrenan antes de cada mes evaluado, con embargo adicional de un día;
se requieren >=100 partidos únicos y >=20 partidos con cada clase en el entrenamiento.
Cada partido tiene peso total uno aunque aporte varias líneas. Under/No es complemento del Over/Sí calibrado;
se preserva monotonía entre líneas. No se calibran 1X2 ni OU con pushes mediante mapas binarios incoherentes.
Se comparan ambos candidatos, sin seleccionar ni activar automáticamente uno de ellos.

Comparación OOS mensual sobre exactamente las filas donde pudieron ajustarse ambos calibradores:

{tabla(experiment) if len(experiment) else 'Sin suficiente historial para ajustar calibradores.'}

Período final declarado antes de ejecutar: desde {manifest['holdout_desde']} (2026–27 europea / Apertura MX).
Los ajustes se siguen actualizando solo con meses anteriores; es evaluación prequential, no calibrador estático.
No se selecciona un método por sus resultados en este período.

{tabla(holdout) if len(holdout) else 'Sin muestra suficiente en el período final.'}

Las diferencias emparejadas e IC semanales se exportan en `calibradores_bootstrap*.csv`;
en esos archivos delta=actual−calibrador, de modo que positivo favorece al calibrador.
Las diferencias requieren consistencia por liga/mes y más temporadas. Las mejoras agregadas, por sí solas,
no autorizan instalar un calibrador. Los parámetros y los cortes de entrenamiento se guardan en `calibradores.json`.

## Ranking descriptivo de mercados

Ordena primero suficiencia (>=300 partidos, >=3 meses y >=20 observaciones de la clase minoritaria),
después habilidad frente a liga, calibración, estabilidad mensual y tamaño de muestra.
No mezcla esos criterios en una puntuación arbitraria ni declara rentabilidad. ECE es la media ponderada
de gaps absolutos por bin/clase en las curvas agrupadas; puede ocultar heterogeneidad entre ligas.
IC por familia/lado en `bootstrap_mercados.csv` acompañan al ranking sin corregir múltiples comparaciones.
En OU entero la clase minoritaria puede ser push; las líneas por partido no aumentan los partidos únicos.

{tabla(ranks[['orden_descriptivo','metrica','kind','lado','partidos','skill_vs_liga','ece','fraccion_meses_mejor_liga','evidencia','ic95_lo','ic95_hi']])}

## Visualizaciones

{chr(10).join(f'![{name}]({name})' for name in names)}

## Limitaciones y Fase 3

1. Prioridad máxima: registrar predicciones y cuotas con fixture_id estable, kickoff UTC completo,
   datos disponibles-as-of, versión del modelo, timestamp de captura, bookmaker, reglas y cuota de cierre.
   EV/ROI/yield/CLV/drawdown económicos no se calculan por falta de cuotas verificables.
2. Obtener varias temporadas con procedencia y revisiones conservadas; validar especialmente ESPN y tarjetas.
3. Evaluar candidatos de calibración con más bloques temporales y estabilidad por liga antes de adoptar uno.
4. Investigar medias y dispersión de tiros/tiros a puerta/tarjetas; comparar binomial negativa fuera de muestra
   si el diagnóstico condicional lo justifica. Priorizar eventos raros y lambdas cero: una binomial negativa con media cero tampoco resuelve esos ceros.
   Evaluar encogimiento con validación temporal antes de atribuir todo el error a Poisson; no ajustar aquí.
5. El período final es pequeño por liga. IC bootstrap son descriptivos y hay múltiples comparaciones;
   el estudio no equivale a datos prospectivos inéditos ni a validación económica.
6. No se reconstruye calendario/jornada oficial ni disponibilidad de la información antes del kickoff.
   Los snapshots actuales podrían incorporar correcciones posteriores. Los cortes evitan usar filas futuras,
   pero no prueban la ausencia de revisiones históricas.

## Reproducción

```bash
python -m pip install -r requirements-dev.txt
python -m evaluacion --salida docs/fase2 --procesos 2 --guardar-predicciones
python -m pytest -q
```

No hay dependencias nuevas: pandas/numpy/scipy/matplotlib ya pertenecen a la aplicación.
`--guardar-predicciones` genera CSV gzip de mercados y conteos; los registros completos son artefactos
regenerables y no se versionan. Se versionan tablas, gráficas, parámetros y manifest con hashes de entrada.
Semillas, período final y parámetros se fijan en la CLI. No hay descargas ni escrituras en servicios externos.
'''
    (out/'REPORTE.md').write_text(report)
    return comparison,ranks

# Conclusiones de Fase 2 y prioridades

Este documento interpreta los resultados del [reporte reproducible](fase2/REPORTE.md).
Las tablas completas, cortes, parámetros y hashes están en `docs/fase2/`.
La evaluación es retrospectiva con entrenamiento temporal; no reconstruye disponibilidad
original de estadísticas ni demuestra rentabilidad. El modelo de producción permanece intacto.

## Qué mercados tienen más potencial predictivo

La muestra principal tiene **1.545 partidos únicos** con al menos cinco encuentros
previos de cada equipo en su condición. El ranking agrupa ligas y líneas fijas:
no debe extrapolarse automáticamente a una liga o línea concreta.

| Familia | Brier actual | Brier liga | Habilidad relativa | IC95 de delta Brier actual−liga | Lectura |
|---|---:|---:|---:|---|---|
| Tiros del local, OU | 0,162186 | 0,175542 | +7,61% | [−0,020281; −0,006291] | Mejor candidato exploratorio; menor Brier que liga en los 11 meses observados |
| Tiros a puerta del local, OU | 0,164017 | 0,169392 | +3,17% | [−0,011470; +0,000392] | Señal puntual favorable, incertidumbre compatible con ausencia de mejora |
| Goles del partido, 1X2 | 0,317695 | 0,326324 | +2,64% | [−0,017957; +0,000961] | Señal exploratoria; no supera claramente todas las referencias |

Los IC se calculan con remuestreo semanal emparejado sobre partidos, no sobre
cada selección como si fuera independiente. Son descriptivos, sin corrección por
múltiples comparaciones ni garantía de capturar dependencia persistente entre semanas.
**No hay mercados certificados como rentables o suficientemente seguros para apostar.**

La ventaja no se extiende a todos los mercados de tiros: el total del partido
es peor que la referencia de liga (Brier 0,136210 frente a 0,130931).
En el agregado de tiros, delta Brier=−0,002083 y su IC95 [−0,006071; +0,001812]
incluye cero; el Log Loss tampoco mejora frente a liga (0,510687 vs 0,508840).
No se debe presentar “tiros” como un bloque uniformemente superior.

En las demás métricas agregadas el modelo actual tiene peor Brier que la referencia
de liga: goles, ambos tiempos, tiros a puerta, amarillas, córners y rojas.
Ese agregado mezcla familias; consulte segmentos por liga/lado/línea antes de generalizar.

## La sobreconfianza se confirma descriptivamente

Para selecciones binarias con probabilidad >=80%, tomando el lado más probable:

| Métrica | Probabilidad media | Frecuencia observada | Exceso de confianza |
|---|---:|---:|---:|
| Goles | 91,13% | 86,57% | 4,56 puntos |
| Goles 1T | 92,77% | 87,55% | 5,21 puntos |
| Goles 2T | 91,34% | 85,02% | 6,32 puntos |
| Tiros | 95,39% | 91,40% | 3,98 puntos |
| Tiros a puerta | 92,61% | 88,90% | 3,71 puntos |
| Amarillas | 89,36% | 85,33% | 4,03 puntos |
| Córners | 92,10% | 84,57% | 7,53 puntos |
| Rojas | 96,39% | 91,19% | 5,20 puntos |

Son medias descriptivas sobre selecciones correlacionadas de una rejilla fija,
no intervalos de confianza ni porcentajes de beneficio. Las tablas registran
partidos únicos y número de selecciones. Las gráficas no conectan bins con menos
de 30 partidos; esos puntos se muestran como cruces grises y se conservan en los CSV.

## Los ceros estructurales son una debilidad prioritaria

En rojas, **139 de los 1.545 partidos maduros** tuvieron un conteo conjunto al que
el modelo actual asignaba probabilidad cero. Esto genera likelihood de conteos
e infinito Log Loss estrictos. En mercados de rojas se registran 458 selecciones
con clase observada de probabilidad cero: **no son 458 partidos distintos**.
También ocurre en goles y sus tiempos. No se oculta con un epsilon en el score principal.

Son ceros del modelo al estimar alguna lambda como cero, no evidencia de que el
suceso sea imposible. Una binomial negativa con la misma media cero tampoco
resolvería el problema. Antes de cambiar distribuciones, Fase 3 debe evaluar
encogimiento o priors para las medias, seleccionados temporalmente fuera de muestra.
No se cambia K_ENCOGE ni ninguna lambda en esta fase.

## Poisson subestima varias colas, pero no basta para elegir su reemplazo

Para tiros del local, la media del residuo de Pearson² está entre **1,76 y 2,14**
según liga. La probabilidad predicha de exceder el cuantil 99 es aproximadamente
**0,73–0,76%**, mientras la frecuencia observada es **3,24–5,71%**.
El porcentaje nominal no es exactamente 1% por la naturaleza discreta del conteo.
Córners presenta un patrón similar; tiros a puerta también muestra dispersión
condicional superior a uno en las seis ligas.

Esto justifica comparar modelos más flexibles, pero puede reflejar error en las
medias, incertidumbre de estimación o covariación no explicada. No demuestra que
binomial negativa vaya a mejorar. La selección deberá contrastar esas causas en
ventanas temporales con las mismas observaciones.

La corrección Dixon–Coles mejora ligeramente el Brier agregado de goles frente a
las mismas lambdas sin DC (delta≈−0,000082). La magnitud es pequeña y no compensa
la inferioridad frente a referencias simples en otras familias. En 1T no hay
mejora concluyente; en métricas sin DC los modelos son idénticos, como corresponde.

## Calibración: señales útiles, sin candidato universal

Se entrenan mapas solo con información anterior al mes evaluado y un día adicional
de embargo. El período final, desde julio de 2026, contiene **213 partidos únicos**
madurados y apenas **9 bloques semanales**. Se evalúan los dos métodos sin elegir
uno con conocimiento del período final y sin instalarlos en producción.

Platt reduce Brier en el período final para amarillas (0,178587→0,177413),
córners (0,179892→0,175795) y tiros (0,128615→0,124161), con IC descriptivos de
mejora que no incluyen cero. Los demás resultados requieren mayor muestra y
consistencia por liga/mes. En rojas Platt **empeora Brier** (0,112474→0,115067),
aunque convierte el Log Loss infinito en finito: distintos scores revelan trade-offs.

Isotónica mejora algunos Brier, pero produce nuevos ceros observados en amarillas,
córners y tiros del período final, dejando Log Loss estricto infinito en esos grupos.
No se debe escogerla solamente por el promedio Brier. Consulte
`calibradores_bootstrap_holdout.csv` y `calibradores_ligas.csv` para valorar
incertidumbre y heterogeneidad. La calibración de mercados no repara automáticamente
la distribución de conteos ni crea una ventaja económica.

## Recomendaciones priorizadas para Fase 3

1. Registrar predicciones, versiones, disponibilidad de datos y cuotas con timestamps
   verificables, ID oficial de partido y reglas de liquidación; ampliar varias temporadas.
2. Resolver experimentalmente los ceros estructurales mediante estimación de medias
   con regularización/priors, incluyendo nuevos equipos y métricas escasas. Mantener
   un período de prueba futuro y comparar con medias de liga y móvil.
3. Revalidar Platt por familia y liga con más bloques temporales; investigar regularización
   de isotónica antes de considerar una adopción. No activar un calibrador universal.
4. Comparar Poisson con alternativas de dispersión para tiros/córners/tarjetas, separando
   errores en medias de errores en varianza. Priorizar tiros del local como candidato,
   conservando controles negativos como tiros totales y tarjetas rojas.
5. Evaluar dinero solo cuando existan cuotas prepartido reales, reglas homogéneas y
   captura de cierre. Hoy no pueden calcularse ROI, yield, CLV ni drawdown verificables.

## Validación del software

**95 pruebas Python** y **3 pruebas web** aprobadas localmente; TypeScript y build
Next.js correctos. Las pruebas incluyen fuga por filas futuras, entrenamiento por
fecha, equivalencia Fase 1, pushes, calibración temporal, scores estructurales,
bootstrap, fronteras exactas de bins, caché íntegra y CLI/reportes/gráficas.
Persiste un aviso de deprecación Starlette/TestClient ajeno a esta implementación.

Una ejecución completa de las seis ligas tardó aproximadamente 9 minutos en el
entorno de esta revisión; regenerar análisis desde registros verificados tarda
aproximadamente 1–2 minutos. Es una medición local, no un benchmark de producción.

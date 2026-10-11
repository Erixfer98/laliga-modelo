# Motor de evaluación histórica (Fase 2)

El paquete `evaluacion/` es independiente de la aplicación. No modifica lambdas,
Dixon–Coles, Kelly, datos, API ni pantallas. El antiguo `backtest.py` sigue disponible
por compatibilidad; sus referencias calculadas con resultados del conjunto evaluado
no deben utilizarse como baselines fuera de muestra. El nuevo motor las reemplaza.

## Ejecutar

Desde la raíz del repositorio, con Python 3.12:

```bash
python -m pip install -r requirements-dev.txt
python -m evaluacion --salida docs/fase2 --procesos 2 --guardar-predicciones
python -m pytest -q
```

Se puede pasar `--datos datos/bbdd_laliga.csv` para evaluar una liga o `--procesos 1`
para ejecución secuencial. Después de guardar registros completos se puede ejecutar
`python -m evaluacion --salida docs/fase2 --reusar-predicciones` para regenerar
solo métricas, calibración y figuras. La caché exige hashes válidos de datos, motor
y archivos; si cambian, obliga a recalcular. `--holdout-desde 2026-07-01` fija el período final; debe
establecerse antes de examinar scores, no elegirse para favorecer resultados.

`manifest.json` identifica versiones numéricas, hashes de código y datos, parámetros,
semillas y configuración. Para reproducibilidad numérica estricta deben usarse las
versiones del manifest: las dependencias generales de la app aún no tienen lockfile.
El tiempo depende del hardware; cada liga se procesa una vez por fecha y métrica,
con una tabla de fuerzas compartida entre los encuentros de ese día. Los procesos
se limitan a dos por defecto; no se ejecuta la rejilla de incertidumbre de 49 puntos,
porque esta fase evalúa probabilidades centrales, no cobertura de sus rangos.

## Módulos y contratos

- `datos.py`: fechas, conteos, integridad, identidad derivada de partido y hashes.
- `temporal.py`: historial estrictamente anterior a la fecha, fuerzas Fase 1,
  cuatro modelos, abstenciones, conteos y diagnósticos de colas.
- `mercados.py`: líneas fijas declaradas ex ante y líneas por defecto de la app;
  máscaras de Fase 1 y resultados observados sin convertir pushes en aciertos.
- `metricas.py`: scores, muestras comunes, calibración, segmentos y bootstrap.
- `calibradores.py`: Platt e isotónica experimentales, con cortes mensuales y embargo.
- `reportes.py`: tablas, figuras y conclusiones con sus límites.
- `__main__.py`: orquestación y CLI reproducible, sin descargas ni despliegues.

`fixture_id` es un hash derivado de liga/fecha/local/visitante. No equivale a un ID
oficial estable frente a aplazamientos o cambios de nombres. Las predicciones de
mercados se identifican por fixture_id/métrica/modelo/tipo/lado/línea. Guardan fecha,
train_max_fecha, equipos, temporada, muestra previa, probabilidades p0/p1/p2 y clase
observada. Las lambdas, los conteos reales, el soporte y la masa excluida están en
`predicciones_conteos.csv.gz`, enlazable por fixture_id/métrica/modelo.

OU se registra una vez como Under/Push/Over: p2 es P(Over), p1 es P(push), p0 es
P(Under). Ambas direcciones se recuperan sin duplicar el registro ni usar un
complemento inválido. En media línea p1=0. BTTS registra No/Sí; 1X2 registra
Visitante/Empate/Local. p1 en 1X2 es empate, **no devolución**. Las curvas y tablas
conocen el tipo de mercado y respetan esa distinción.

Los CSV completos de predicciones son artefactos locales regenerables, ignorados
por git por su tamaño. Tablas agregadas, parámetros, manifest y PNG se versionan
junto al [reporte de resultados](fase2/REPORTE.md).

## Pruebas y decisiones estadísticas

Las pruebas comprueban que modificar resultados futuros no altera predicciones
anteriores; que ambos encuentros del mismo día quedan fuera del entrenamiento;
que las lambdas y probabilidades coinciden con Fase 1; que no se sustituye un equipo
desconocido dentro del modelo actual; y que datos inválidos fallan explícitamente.
Incluyen scores de pushes, ceros estructurales, PAVA ponderado con empates, Platt
contra un oráculo analítico, ajuste temporal sin resultados del mes de prueba,
bootstrap reproducible y una ejecución integrada de CLI/reportes/gráficas.

Las líneas múltiples están correlacionadas. Se informa el número de partidos
únicos y se promedian selecciones por partido antes de comparar modelos mediante
bootstrap de semanas. Los IC son descriptivos: no corrigen múltiples comparaciones
ni garantizan capturar dependencias persistentes entre semanas. El ranking no es
una validación económica ni un permiso para apostar.

No se selecciona un calibrador a posteriori por su score en el período final.
Ambos candidatos se evalúan como experimentos prequential: para cada mes se
entrenan solo con meses previos, excluyendo además el día anterior al inicio del
mes. La inferencia debe complementarse con estabilidad por liga y período, más
historia y registros prospectivos antes de cambiar producción.

## Datos que faltan para una evaluación económica

Debe empezar a capturarse, sin sustituir el resultado por una cuota inventada:

| Registro | Campos mínimos |
|---|---|
| Fixture | ID oficial, liga, equipos, kickoff UTC completo, fase, alcance 90 minutos |
| Predicción | predicted_at UTC, train_cutoff UTC, datos/hash/versiones, lambda, vector de probabilidades, regla/línea |
| Cuota | bookmaker, captured_at UTC anterior al kickoff, cuota decimal, selección, reglas y estado |
| Cierre | timestamp, cuota de cierre, mismo mercado y regla para comparar CLV |
| Liquidación | resultado validado, win/push/loss, retorno efectivo y regla de la casa |

Sin ese contrato no se calculan ROI, yield, drawdown ni CLV. Los históricos actuales
no guardan timestamps de publicación ni revisiones completas: la evaluación es
retrospectiva con entrenamiento temporal, no replay certificado de apuestas reales.

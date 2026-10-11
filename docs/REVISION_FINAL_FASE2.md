# Revisión técnica final del PR #2

## Dictamen

Listo para merge como herramienta independiente de evaluación retrospectiva de Fase 2,
sujeto a los checks del commit final. No autoriza activar calibradores, apostar con el ranking
ni desplegar. No se ha hecho merge ni despliegue.

## Hallazgos y correcciones

1. El filtro previo solo exigía cuatro nombres distintos: podía aceptar un modelo desconocido,
   duplicados o resultados observados incompatibles. Se añade un contrato que exige los cuatro
   modelos declarados, una fila por partido/métrica/mercado/lado/línea y coincidencia de objetivos,
   fechas, liga y banderas de elegibilidad. Claves faltantes e inconsistencias detienen la evaluación.
2. Los diagnósticos de conteos usaban las filas disponibles de cada modelo, potencialmente distintas
   ante errores parciales. Ahora requieren la misma cohorte partido/métrica para los cuatro modelos.
3. El bootstrap promediaba antes de emparejar: ante líneas ausentes, compartir un partido no bastaba.
   Ahora intersecta mercados exactos para todos los modelos antes de promediar por partido y
   remuestrear semanas. Un caso automatizado introduce una línea extrema y la elimina en una
   referencia: el valor extremo no contamina la diferencia del mercado realmente comparable.
4. Las comparaciones de calibradores también exigen una tripleta única actual/Platt/isotónica sobre
   la misma clave y objetivo. Se exportan auditorías de cohortes para mercados, conteos y calibradores.
5. Fechas de entrenamiento ausentes, iguales o posteriores a la predicción se rechazan antes de
   calibrar y al evaluar predicciones nuevas o recuperadas del caché.

## Resultado de la auditoría histórica

Los 1.423.144 registros de mercados y 68.000 registros de conteos satisfacen los contratos.
Los cuatro modelos comparten exactamente las claves de mercados y objetivos: no hay exclusiones
por fallos parciales en esta ejecución. Cada métrica tiene 2.125 partidos evaluables por modelo.
La muestra principal sigue siendo 1.545 partidos con suficiente historial; las exclusiones iniciales
se registran como abstenciones compartidas, sin imputación ni fallback exclusivo del modelo actual.

La comparación es válida dentro de esa cohorte condicional. No prueba ausencia de sesgo de selección
respecto a los 72 partidos sin historial evaluable o respecto a otras temporadas. Los datos corruptos
hacen fallar la ejecución en lugar de convertirse silenciosamente en ceros o exclusiones.

## Calibración e interpretación

El modelo base usa solo filas anteriores al día evaluado. Los mapas mensuales usan predicciones y
resultados de fechas anteriores al inicio del mes, con un día adicional de embargo. Las pruebas
alteran tanto probabilidades como resultados futuros y comprueban que las predicciones calibradas
anteriores no cambian. El período final es prequential: permite actualizar con meses ya concluidos;
no es una evaluación de un mapa estático congelado. No se selecciona automáticamente un ganador.

Estas son mejoras retrospectivas fuera de muestra por corte temporal, no una certificación as-of:
los archivos actuales podrían incorporar revisiones históricas y faltan timestamps de disponibilidad.
Los intervalos son exploratorios, sin corrección por múltiples comparaciones. La selección posterior
de mercados prometedores necesita una evaluación prospectiva independiente.

El ranking mide calidad predictiva y declara pendiente el potencial económico. Sin cuotas y reglas
históricas verificables no se infieren EV, ROI, Kelly, CLV ni rentabilidad. Los mapas experimentales
siguen dentro de `evaluacion/`; los archivos de aplicación, API y motor de producción no cambian.
Una prueba adicional prohíbe importar el evaluador desde los módulos principales de producción.

## Validación

- 105 pruebas Python aprobadas, incluyendo 29 pruebas del evaluador (10 casos nuevos).
- 3 pruebas web aprobadas; TypeScript y build Next.js aprobados.
- Un aviso preexistente de deprecación Starlette/TestClient, sin fallos.
- Reejecución de informes desde predicciones con hashes verificados; contratos nuevos aplicados
  a todos los registros. Las conclusiones numéricas no cambian si las cohortes están completas.
- Auditorías reproducibles: `docs/fase2/comparabilidad_*.csv`; procedencia: `manifest.json`.

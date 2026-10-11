## Endpoint local (FastAPI TestClient)

| Caso | n por versión | Antes media / mediana / p95 (ms) | Después media / mediana / p95 (ms) | Reducción de mediana |
|---|---:|---:|---:|---:|
| fria | 3 | 1172.6 / 549.1 / 2516.2 | 523.5 / 489.3 / 599.8 | No concluyente |
| repetida | 30 | 399.7 / 325.7 / 871.9 | 32.3 / 29.7 / 46.3 | 90.9% |
| grupo | 30 | 318.8 / 272.0 / 447.6 | 33.8 / 31.4 / 52.6 | 88.4% |
| mercado | 30 | 300.7 / 264.8 / 387.9 | 34.3 / 30.0 / 36.9 | 88.7% |
| lineas | 30 | 408.4 / 308.4 / 990.7 | 42.4 / 31.2 / 137.6 | 89.9% |

Las peticiones frías son frías para la caché de análisis, no arranques independientes del intérprete; el orden antes/después y n=3 impiden atribuir con rigor una mejora fría. La fila `lineas` mezcla la primera configuración nueva por métrica con nueve repeticiones: no son treinta configuraciones nuevas.

| Modo usado por la interfaz | n | Media / mediana / p95 HTTP (ms) | Tamaño mínimo–máximo |
|---|---:|---:|---:|
| resumen | 30 | 22.2 / 22.3 / 30.0 | 60,638–82,759 bytes |
| detalle | 30 | 18.6 / 17.3 / 26.8 | 6,662–8,098 bytes |

## Etapas en una petición completa repetida

Medianas sobre 30 peticiones; las etapas ausentes valen cero porque se reutilizan. No se deben sumar medianas para reconstruir la mediana del total.

| Etapa | Antes (ms) | Después (ms) |
|---|---:|---:|
| fuerzas | 119.541 | 0.000 |
| lambdas | 0.897 | 0.000 |
| distribuciones | 48.179 | 0.000 |
| mercados | 26.683 | 0.000 |
| graficos | 0.624 | 0.501 |
| detalle | 3.400 | 3.079 |
| conversion_json | 9.269 | 8.543 |
| serializacion | 2.690 | 2.393 |

La referencia ejecutó 51 construcciones de distribución en el caso de goles observado: rejilla de 49 puntos, centro añadido y distribución central. Después, una petición repetida no vuelve a ejecutar fuerzas, lambdas, distribuciones ni cálculo de probabilidades.

## Recorrido automatizado antes/después

Incluye la acción de Playwright y dos frames de pintura; diez interacciones por celda. La instrumentación adicional posterior introduce un pequeño coste de observación: la comparación es conservadora, no una medición aislada de React.

| Ancho | Acción | Antes media / mediana / p95 (ms) | Después media / mediana / p95 (ms) | Reducción de mediana |
|---:|---|---:|---:|---:|
| 390 | mercado | 1203.7 / 1367.0 / 1651.4 | 220.0 / 205.7 / 385.5 | 85.0% |
| 390 | grupo | 806.8 / 839.4 / 1069.0 | 214.7 / 211.3 / 297.3 | 74.8% |
| 390 | linea | 646.1 / 576.8 / 1006.0 | 409.9 / 382.5 / 527.5 | 33.7% |
| 390 | metrica | 938.9 / 936.6 / 1424.7 | 606.0 / 449.0 / 1347.1 | 52.1% |
| 1440 | mercado | 864.3 / 957.6 / 1231.4 | 510.1 / 302.4 / 1981.5 | 68.4% |
| 1440 | grupo | 944.8 / 1025.4 / 1164.7 | 314.6 / 310.2 / 398.7 | 69.7% |
| 1440 | linea | 1039.9 / 1101.2 / 1650.1 | 552.2 / 582.9 / 721.6 | 47.1% |
| 1440 | metrica | 962.8 / 946.5 / 1035.5 | 667.5 / 491.3 / 2002.4 | 48.1% |

## Latencia visible desde pointerdown, versión optimizada

Medida dentro del navegador hasta cambio de selección y probabilidad válida más dos frames. No incluye el posicionamiento previo del puntero ni la espera previa de Playwright. No existe medición equivalente de pointerdown para la versión anterior: no se calcula una mejora porcentual con series distintas.

| Ancho | Acción | Media / mediana / p95 (ms) |
|---:|---|---:|
| 390 | mercado | 32.5 / 31.4 / 43.6 |
| 390 | grupo | 57.2 / 47.6 / 163.2 |
| 390 | linea | 297.8 / 273.5 / 441.8 |
| 390 | metrica | 362.5 / 261.4 / 1112.9 |
| 1440 | mercado | 62.4 / 55.4 / 155.1 |
| 1440 | grupo | 69.1 / 58.8 / 123.7 |
| 1440 | linea | 367.5 / 393.7 / 544.2 |
| 1440 | metrica | 245.8 / 236.5 / 385.7 |

Mercados y grupos cumplen la referencia de 100 ms en la mediana de ambos tamaños, pero no en todos los p95. La mediana de líneas es inferior a 300 ms en móvil y superior en escritorio; el p95 no cumple en ninguno. El endpoint con distribuciones reutilizadas sí queda por debajo de 300 ms en todas las muestras de este piloto. No se declara cumplida la meta de latencia total de líneas en escritorio ni se garantiza un SLA en producción.

Los cambios de mercado/grupo no generan peticiones de resumen: únicamente solicitan el detalle secundario (habitualmente una). Líneas y métricas solicitan resumen y detalle; los ajustes consecutivos de línea se agrupan por debounce y las solicitudes obsoletas se abortan. La serie de métricas incluye el primer cambio a corners; debe separarse de las repeticiones al interpretarla.

Memoria máxima residente del proceso del benchmark: 187.9 MiB. Tamaño estimado retenido al finalizar: modelos 6.8 MiB, mercados 7.7 MiB y vistas 7.3 MiB. Incluye instrumentación y librerías; no es una garantía de RSS bajo cualquier carga.

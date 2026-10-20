# Kuota: rendimiento de la navegación entre mercados

Rama `fix/kuota-rendimiento-mercados`, base `main` (`c31f6cf`). No merge ni despliegue. Las mediciones corresponden al entorno local, no al hosting público.

## Diagnóstico y arquitectura

La pantalla enviaba mercado y grupo como parámetros del mismo GET que reconstruía el análisis completo. `useApi` retiraba el resultado anterior y la pantalla desmontaba los controles mientras esperaba. `vista_partido` recalculaba fuerzas, lambdas, distribución central, rejilla 7×7 más centro, todos los mercados, históricos, gráficos y textos de contexto. La incertidumbre por métrica ya estaba cacheada, pero no el análisis del enfrentamiento.

Las mediciones diferencian fuerzas (preparación estadística), lambdas, distribuciones, mercados, gráficos, estadísticas de detalle, conversión a tipos JSON, serialización JSON y recorrido HTTP local. La mayor parte de la espera era trabajo Python evitable y la dependencia de la actualización visual respecto a la petición completa. No se atribuye a Render, Vercel o a la red del usuario una latencia que no se midió allí.

El endpoint existente conserva su modo completo por defecto y añade dos modos optativos: `resumen` (todos los mercados evaluados, sin gráficos ni textos del analista) y `detalle` (únicamente la selección, gráfico y sus históricos). La pantalla selecciona probabilidades, devoluciones, escenarios y calificación desde el resumen ya recibido. El detalle sigue siendo calculado en Python y llega por separado. Un tercer modo ligero, `version`, verifica la vigencia antes de guardar una selección sin recalcular el modelo. No se duplican fórmulas en JavaScript.

Tres cachés LRU por proceso reutilizan: modelo y distribuciones (12 entradas, presupuesto estimado 32 MiB), probabilidades por regla (512 entradas, 16 MiB), análisis evaluado por configuración/historial (24 entradas, 32 MiB). El tamaño cuenta arrays y memoria profunda de DataFrames; es un presupuesto de objetos estimado, no un límite del RSS del intérprete. Los resultados demasiado grandes no se retienen. Las máscaras capturadas por las funciones también se contabilizan. Los fallos no se guardan.

Cada caché protege el cálculo mediante un bloqueo: los misses se serializan y una clave residente se calcula una sola vez. Un semáforo admite como máximo dos análisis de partido simultáneos por proceso, limitando las distribuciones transitorias retenidas por solicitudes concurrentes. Las cachés son independientes por worker y no requieren Redis. Las entradas antiguas se expulsan por capacidad; una actualización jamás las vuelve a utilizar.

Las claves incluyen liga, ambos equipos y su orden, métrica, SHA-256 de la instantánea CSV, código del análisis, versión probabilística y parámetros (`XI`, `RHO`, métricas y soportes). Las vistas añaden configuración completa de líneas, tamaño y filtro del historial. Una lectura detecta cambios de mtime/ctime en nanosegundos, tamaño e inode y verifica que el archivo no haya cambiado mientras se leía. El CSV se analiza desde los mismos bytes que se identifican con el hash. La versión que recibe el navegador identifica datos y modelo; un detalle solicitado con otra versión devuelve HTTP 409.

La caché optativa del navegador conserva hasta ocho respuestas durante 30 segundos, con un presupuesto de representación estimado de 2 MiB. Siempre revalida en el servidor; el boleto está bloqueado mientras haya análisis o detalle pendiente y ante errores. Al pulsar añadir se consulta además la versión vigente; si cambió, se rechaza el registro y se actualiza el análisis. Un cambio de contexto durante esa verificación cancela la solicitud e impide añadir la selección anterior. Una clave de detalle incluye selección, líneas, filtros y versión. Las respuestas abortadas no se muestran ni se guardan. Los otros consumidores de `useApi` siguen sin caché por defecto.

Los cambios consecutivos de líneas se agrupan con un debounce de 120 ms. La línea elegida se actualiza de inmediato; las probabilidades pendientes se señalan y no autorizan el boleto. No hay debounce para mercados, grupos ni métricas. Los cambios de liga, equipos o métrica no conservan un resultado perteneciente al contexto anterior. Los controles del mismo enfrentamiento permanecen montados durante ajustes de líneas e historial.

## Integridad matemática

No se modificaron `modelo.py`, `probabilidades.py`, las fórmulas de Poisson/Dixon–Coles, lambdas, rejilla de sensibilidad, liquidaciones, probabilidades conjuntas, EV ni Kelly. Tampoco datos, autenticación, persistencia ni modelos experimentales. La reorganización de `kuota.py` permite inyectar resultados previamente calculados; las operaciones aritméticas y su orden se conservan.

El benchmark carga el código anterior de `kuota.py` y `api.py` desde el commit base y lo compara con el endpoint optimizado: 108 contextos (seis ligas × nueve métricas × dos configuraciones) coinciden exactamente en todo el JSON previo, incluidos todos los mercados y escenarios. `data_version` es metadato nuevo y se excluye de esa comparación.

Las pruebas automatizadas comparan el recorrido sin caché contra completo, resumen y detalle sobre dos enfrentamientos, todas las métricas, líneas enteras y medias, dos filtros e históricos de ocho partidos. Recorren cada mercado y gráfico. Tolerancias: absoluta `1e-14`, relativa `1e-13`, con igualdad de claves, orden y valores no numéricos. También cubren invalidación por cambios reales del CSV y parámetros, contexto invertido, cálculo concurrente único, límites y errores.

## Mediciones

Se publican las muestras crudas en `docs/rendimiento/`. Los benchmarks se ejecutan secuencialmente, separados de las pruebas de navegador/Python. El p95 es el percentil empírico por rango más cercano. Las muestras frías son tres contextos; ese tamaño no permite estimar de forma robusta una cola de latencia.

La latencia HTTP del servidor se mide mediante FastAPI TestClient y no incluye red remota. La latencia visible usa Chromium real, compilación de producción local, viewports 390 y 1440 px, acción de Playwright, espera de la selección correspondiente y dos frames para pintar. El campo `ms` incluye automatización y espera visual; `visible_ms` mide dentro del navegador desde pointerdown hasta el cambio de selección/probabilidad, seguido de dos frames. No equivalen a un perfil del reconciliador de React ni a un iPhone físico/Safari. Los cambios de métrica esperan la respuesta revalidada, no sólo la aparición del resultado cacheado.

Para reproducir:

```bash
python scripts/benchmark_rendimiento.py --reference c31f6cf --output work/rendimiento/servidor.json
# API local en :8000 y build de producción web en :3103, sin otras cargas de benchmark
(Script retirado el 20/10/2026 con la pantalla única de partido: ahora las 9 métricas se piden una vez por partido, en modo=compacto.)
```

El script de referencia requiere que el commit base esté disponible localmente. No se impone un umbral temporal frágil en CI compartida; las pruebas sí verifican ausencia de peticiones redundantes del análisis base y resultados correctos bajo demoras deliberadas.

## Cambios de contexto y registro del boleto

La prueba de navegación retiene deliberadamente la respuesta del detalle: verifica que selección y grupo cambien sin esperar, que no aparezca una nueva petición de resumen y que el boleto quede bloqueado hasta validar el detalle. Una segunda prueba encadena líneas y cambia de grupo con una actualización pendiente, comprobando que se conserven las líneas de ambos grupos. Las pruebas de contexto cambian el equipo durante una consulta y durante una verificación de registro, y comprueban que sólo se guarde la selección final. También se simula HTTP 409 justo al añadir: no se guarda ninguna selección.

El protocolo nuevo es optativo. Los consumidores existentes pueden seguir solicitando la vista completa y conservan todos sus campos anteriores, con un metadato adicional de versión. La comprobación de versión no realiza fuerzas, lambdas, sensibilidad ni evaluación de mercados. Los avisos diferencian una actualización de datos de un error de conexión.

## Resultados completos y límites

La [tabla comparativa](rendimiento/tablas.md) contiene media, mediana, p95 y reducción porcentual; las muestras están en [servidor.json](rendimiento/servidor.json), [usuario-antes.json](rendimiento/usuario-antes.json) y [usuario-despues.json](rendimiento/usuario-despues.json). El piloto final contiene 306 peticiones instrumentadas y 80 interacciones en cada versión de la interfaz.

Las medianas visibles de mercado son 31 ms en móvil y 55 ms en escritorio; las de grupo, 48 y 59 ms. No se cumplió la referencia en todos los p95. Las líneas tienen mediana visible de 274 ms en móvil y 394 ms en escritorio: la referencia de 300 ms de latencia total sigue pendiente en escritorio y en los p95. La latencia local del endpoint reutilizado es mucho menor; no se confunden ambos valores ni se promete el mismo resultado en el hosting público.

No hay un perfil aislado del reconciliador React ni una medición en el hosting remoto: el piloto observa la actualización del DOM y los frames. La reducción demostrada del cálculo Python y del volumen por cambio de selección identifica trabajo redundante concreto; la latencia total residual incluye debounce, transporte local, planificación y renderizado. Sería incorrecto atribuir toda la latencia residual a una de esas etapas sin otra medición.

## Verificación

- Python: 158 pruebas en la ejecución completa, más la prueba reforzada de invalidación que compara las probabilidades nuevas con la instantánea CSV modificada.
- Web: ocho pruebas unitarias; TypeScript sin errores; build de producción local correcto.
- Navegador: diez escenarios críticos finales locales en móvil y escritorio. La batería completa contiene 44 escenarios, incluidos navegación, temas, accesibilidad, métricas, grupos, filtros, líneas, errores y boleto.
- Equivalencia directa contra código base: 108 contextos coinciden exactamente.
- El resultado verificado de la batería completa de navegador y de CI se registra en la descripción y checks del PR, con el commit al que corresponde.

Limitaciones operativas: cachés por proceso (sin compartir entre workers), primera petición sin garantía de aceleración, y presupuestos de memoria estimados que no sustituyen el límite de memoria del hosting. No se modificaron fórmulas para conseguir mejoras de velocidad. No se hicieron merge, despliegue ni activación experimental.

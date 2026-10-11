# Fase 5 B2 — Automatización experimental, sin activación

## Dictamen y disponibilidad

Continúa el PR borrador #6, rama `feature/fase-5-inteligencia-contextual` hacia `main`.
La automatización está implementada y probada con transportes **sintéticos**. No se
realizaron consultas deportivas, contratación, despliegue, merge, ajuste de lambdas
ni ejecución de LLM. La navegación y la selección manual vigentes permanecen intactas.
No se afirma cobertura actual, certificación oficial ni mejora predictiva.

El entorno no tiene clave API-Football ni almacenamiento durable configurado; los
hosts deportivos y meteorológicos no están habilitados por su política de red.
La clave que apareció en una captura debe **revocarse y rotarse antes de operar**.
No pegarla en chats; no conservar la captura con la credencial expuesta.

| Capacidad | Implementado y probado sintéticamente | Validación real / limitación |
|---|---|---|
| Catálogo de seis ligas | Selectores país/nombre, ID consultado, rechazo de ambigüedad | Ningún ID de las seis se declara verificado por Codex |
| Calendario liga/temporada/rango | Permisos explícitos, ventanas acotadas y versiones | Free rechaza temporada 2026 según prueba manual del usuario |
| Consulta global por fecha | Estrategia explícita, fechas autorizadas y volumen acotado | Usuario observó respuestas en dos fechas; no prueba cobertura de las seis ligas |
| Lesiones/suspensiones | Endpoint injuries; hechos reportados con motivo y jugador | Cobertura/plan desconocidos; reporte del proveedor no equivale a confirmación oficial |
| Alineaciones | Endpoint lineups, captura/registro previo, identidad de equipos | Cobertura desconocida; una alineación parcial conserva estado desconocido |
| Alineaciones previstas | Estado explícito desconocido | No existe fuente verificada que las identifique como previstas |
| Plantillas | Squads por ID de equipo, cobertura y presupuesto | Acceso real desconocido; roster no acredita titularidad |
| Clima | Open-Meteo UTC, unidades y procedencia de coordenadas | Sin coordenadas verificadas ni conexión real; nunca se inventan |
| Descanso/congestión | Historial de fixtures archivados as-of | Solo liga observada, otras competiciones ausentes; no descanso desde final del partido |
| Contexto competitivo/rivalidad | Desconocidos explícitos | Sin definiciones y fuentes verificadas |
| Archivo/recuperación | SQLite, bytes originales, hashes, cadenas, backup reabierto | Restauración local sintética; no demuestra durabilidad operacional |
| Dataset para futuro analista | JSON estricto, fuentes, fechas, contradicciones, desconocidos | Sin LLM ni coeficientes/impactos; no reemplaza predicción oficial |

Las pruebas manuales comunicadas por el usuario son observaciones ajenas a esta ejecución:
`/leagues?id=140&season=2024` confirmó cobertura histórica de LaLiga;
fixtures globales del 11 y 12 de octubre de 2026 respondieron;
la consulta de liga/temporada 2026/fecha 12 rechazó el plan Free. Temporada, fecha,
endpoint y suscripción se tratan por separado. No se extrapola acceso actual ni completo.

## Componentes y garantías

- `politica.py`: selectores centrales, límites, formas/valores de consultas y permisos.
  No contiene IDs oficiales precargados. La política de ejemplo deniega todo acceso.
- `cliente.py`: presupuesto persistente anterior a cada intento, reserva, caché,
  exclusión mutua entre procesos, errores JSON HTTP 200, 429/Retry-After, rechazo de
  eco de credenciales y reintentos exclusivamente transitorios, máximo dos.
- `operaciones.py`: captura original deduplicada por hash, recibo append-only con
  registro efectivo posterior a captura, consumo y restricciones persistentes.
- `descubrimiento.py`: seis consultas de catálogo, rango permitido, validación UTC,
  temporadas, identidad exacta ortográfica, cuarentena, versiones y paginación local.
- `evidencia_contextual.py`: capturas permitidas enlazadas a una versión de fixture,
  extracción determinista y contrato `kuota-ai-input-v1`.
- `cli_b2.py`: operación fuera de la web, dry-run predeterminado, autorización explícita.

Una restricción no provoca fallback a otra estrategia. El rechazo de fixtures bloquea
consultas alternativas por ID/globales; no se reintenta el mismo alcance denegado.
Cambiar la política para usar otro endpoint no borra esa restricción. Una futura
reautorización después de contratar otro plan requiere revisión administrativa
explícita; no está implementada su liberación automática ni se recomienda editar SQL.

Los endpoints requieren permisos por separado. `league_seasons` usa IDs obtenidos del
catálogo y temporadas permitidas por el operador tras verificar el plan. La existencia
de un año en el catálogo **no acredita permiso de suscripción**. `global_dates` expresa
fecha permitida y estimación de volumen revisada por el operador: no acredita cobertura.
No se agregan páginas del proveedor, parámetros `page` inexistentes ni consultas masivas.
Respuesta paginada/volumen excesivo se archiva y rechaza; no puede evitarse recibir la
primera respuesta para conocer su volumen. Si la eficiencia global no es defendible,
no autorizar esa estrategia. El inventario local sí pagina (1–100 elementos).

La coincidencia de equipos admite únicamente diferencias de acentos, mayúsculas y
espacios. Conserva nombres internos, hash del CSV y catálogo literal de nombres como
prueba. No usa resultados del CSV para construir factores contextuales. Alias,
abreviaciones, equipos nuevos o correspondencias conflictivas quedan rechazados;
no hay alias inventados ni una afirmación de cobertura total. Resolver un nombre no
coincidente exige incorporar una correspondencia revisada en una futura entrega o
armonizar el catálogo bajo revisión; no buscar IDs por cada enfrentamiento. Se rechaza
que un mismo ID/nombre cambie de identidad dentro de proveedor/liga/temporada.

Cada captura conserva bytes originales incluso si contiene varios fixtures. Repetidos
idénticos se deduplican; repetidos incompatibles se rechazan. Reconsultar caché conserva
la captura y su registro originales. Un cambio de fecha/estado crea versión nueva.
La vista as-of usa la última versión efectivamente registrada al corte: cancelados,
postergados, desconocidos, iniciados y finalizados no entran en futuras predicciones.
Una versión obsoleta no puede generar contexto actual. Fixture histórico observado
ahora no se convierte en evidencia disponible entonces.

El dataset incluye identidad de fixture, equipos, sede, kickoff y registro efectivo,
validados contra su versión; exige captura **y registro** antes del corte y registro antes del kickoff.
Los timestamps publicados pueden permanecer nulos. Las fuentes no se declaran
certificadas por el proveedor/organizador. Ausencia reportada frente a titularidad del
mismo jugador genera contradicción explícita; no se decide automáticamente quién tiene
razón. Una respuesta vacía no prueba ausencia de lesiones. Plantillas/alineaciones
parciales conservan el campo desconocido. `unknown_fields` no certifica completitud de
las listas restantes. Suspensión sigue desconocida como componente completo: los
motivos disponibles quedan en `reported_absence`, sin inferir sanciones oficiales.
La evidencia externa se trata como datos, nunca instrucciones para un agente.

Clima exige un recibo exitoso `/venues` del mismo estadio con latitud/longitud y anterior
al registro meteorológico. Muchos contratos de estadio no proporcionan coordenadas:
si faltan, permanece desconocido. El CLI no inventa geocodificación ni llama un servicio
alternativo. El ciclo consulta `/venues` únicamente si está autorizado y no hay evidencia
previa del estadio; reutiliza el archivo y el presupuesto del cliente. UTC, unidades y hora de kickoff se validan al extraer el dato;
publicación/run ausente queda desconocida. Open-Meteo requiere autorización adicional,
caché de una hora por versión y tope independiente de diez intentos/día, sin reintentos.
Condiciones comerciales/licencia deberán verificarse antes de habilitarlo.

## Configuración segura y operación

1. Rotar la clave expuesta en el portal autorizado. Guardar la nueva únicamente en
   el gestor de secretos del servicio backend, inyectada como `KUOTA_API_FOOTBALL_KEY`.
   No usar `NEXT_PUBLIC`, argumentos de shell, `.env` versionados ni capturas/logs.
2. Aprovisionar volumen persistente y backup independiente. Probar restauración de
   una copia y documentar la referencia operativa. No contratar recursos sin autorización.
3. Configurar `KUOTA_CONTEXT_STORAGE_ROOT`, `KUOTA_CONTEXT_BACKUP_ROOT` y
   `KUOTA_CONTEXT_DURABILITY_EVIDENCE` desde la configuración privada del servicio.
   Se rechazan `/workspace`, `/tmp` y `/dev/shm`; rutas existentes y separadas son
   necesarias, pero no certifican durabilidad física. Un solo archivo por cuenta.
4. Autorizar red a los hosts fijos con TLS/proxy/CA normales. No desactivar TLS ni
   eludir restricciones de la red o suscripción. Archivo privado, usuario de servicio
   restringido, reloj UTC sincronizado, backups externos fuera del repositorio.
5. Copiar `contexto/config/api-football.example.json` a configuración privada. No
   contiene credenciales y todos los flags operativos comienzan en false. Habilitar
   solo `/status` y `/leagues` para la verificación autorizada, sin permisos fixtures.
   Marcar `live_authorized`, `credential_rotated`, `network_authorized` y
   `restore_verified` únicamente después de cumplir y documentar esas condiciones.
   Son declaraciones operativas: el software no certifica que sean verdaderas.
6. Ejecutar conectividad/catálogo con autorización explícita. Revisar IDs/temporadas,
   presupuesto disponible, cobertura y plan. Completar `seasons` por liga interna y
   `policy.league_seasons` usando IDs consultados. En Free, no autorizar temporada
   2026 suponiendo que el catálogo o una consulta global resuelven la restricción.
7. Autorizar solo endpoints/contextos cubiertos. Ejecutar `ciclo` para descubrir y
   capturar automáticamente los fixtures compatibles; no seleccionar cada partido.
   Ejecutar inicialmente ventanas cortas y revisar rechazos/desconocidos.

Ejemplos de rutas operativas, **no provisionadas ni habilitadas aquí**:

```bash
python -m contexto.cli_b2 estado
python -m contexto.cli_b2 --config /etc/kuota/contexto.json --db /var/lib/kuota/contexto.sqlite --dry-run descubrir --desde 2026-10-11 --hasta 2026-10-12
# Los siguientes requieren autorización, configuración y archivo durable real:
python -m contexto.cli_b2 --config /etc/kuota/contexto.json --db /var/lib/kuota/contexto.sqlite --execute conectividad
python -m contexto.cli_b2 --config /etc/kuota/contexto.json --db /var/lib/kuota/contexto.sqlite --execute catalogo
python -m contexto.cli_b2 --config /etc/kuota/contexto.json --db /var/lib/kuota/contexto.sqlite --execute ciclo --desde 2026-10-11 --hasta 2026-10-12
python -m contexto.cli_b2 --db /var/lib/kuota/contexto.sqlite inventario --page 1 --page-size 25
python -m contexto.cli_b2 --db /var/lib/kuota/contexto.sqlite consumo
python -m contexto.cli_b2 --db /var/lib/kuota/contexto.sqlite evidencia --id HASH_DEL_RECIBO_B2
python -m contexto.cli_b2 --db /var/lib/kuota/contexto.sqlite dataset --id HASH_DEL_RECIBO_FIXTURE
python -m contexto.cli_b2 --db /var/lib/kuota/contexto.sqlite verificar
python -m contexto.cli_b2 --db /var/lib/kuota/contexto.sqlite backup --salida /backup/kuota/copia-nueva.sqlite
```

Dry-run no lee la clave ni abre/crea el archivo: muestra selectores y fechas, no simula
IDs o respuestas. `evidencia` es diagnóstico **privado** con respuesta original; no
publicarlo como endpoint público ni enviar su salida a un log compartido. `consumo`
muestra solo categorías seguras de intentos, incluidos reservados ante crash,
errores y restricciones. Los headers de cuota solo reducen el presupuesto conocido.
Solicitudes manuales/u otro archivo de la misma cuenta no son detectables localmente:
centralizar consumidores y verificar saldo; el contador es un límite conservador local,
no certificación del consumo completo del proveedor. Reserva inicial diez de cien.
Caché cinco minutos; no aumenta el límite del proveedor. En límites/minuto, esperar
Retry-After antes de otro ciclo; esperas superiores a un segundo no bloquean el CLI.
Errores permanentes no consumen reintentos automáticos.

### Programación diseñada, deshabilitada

No se instala timer, cron ni GitHub Action de captura. Después de autorización y un
piloto real, un timer del servicio durable debe ejecutar `ciclo` con fechas UTC calculadas
al inicio (ventana máxima configurada), una vez al día inicialmente, un solo worker,
lock compartido, límite de tiempo del proceso, logs solo de códigos/contadores y backup
independiente al terminar. Un timer separado puede capturar contexto más cerca del
kickoff reutilizando IDs y snapshots, siempre dentro del presupuesto. Presupuesto
restante insuficiente produce abstención, no más consultas. Ajustar frecuencia requiere
medir consumo/cobertura real; cien llamadas no permiten prometer investigación completa
de todos los encuentros. No usar disco efímero ni navegación web como disparador.

Una interrupción deja el intento contabilizado conservadoramente; rerun reutiliza
capturas/cache y no duplica recibos idénticos. El transporte sincrónico en vuelo no
puede cancelarse instantáneamente: termina o vence su timeout; el resultado cancelado
no se publica como captura contextual nueva. Las cadenas se verifican antes de usar
fuentes; no son firmas externas ni protección frente a administrador que reescribe
base/reloj completos. El contrato Fase 3 y sus predicciones permanecen intactos.

## Pruebas y piloto

Las pruebas B2 usan IDs arbitrarios y transportes **SINTÉTICOS**; ninguna demuestra
cobertura de API-Football, fechas autorizadas, coordenadas reales o rendimiento WAN.
Incluyen permisos, seis ligas, restricción temporal independiente, errores HTTP 200,
429, reserva, concurrencia/caché, cancelación, eco de clave, archivos dañados, backup,
versionado, UTC, ambigüedad, ausencia, contradicciones, clima y perturbación de evidencia
futura: el dataset al corte previo permanece idéntico salvo fecha de generación.

Piloto local con tracemalloc, 60 fixtures sintéticos/seis ligas: primera ejecución
12.436 s, rerun con caché 0.911 s; 12 solicitudes mock iniciales y cero adicionales,
1.083 MiB de pico Python y SQLite 344064 bytes. **Cero llamadas reales**. Usa catálogo
interno de dos nombres sintéticos: no representa todos los costos operativos. El
informe reproducible y script están en `docs/pilotos/`. La verificación completa de
cadena bajo cada inserción produce crecimiento acumulado cuadrático; este backend
solo se propone para piloto acotado de un nodo. Antes de ampliar volumen, medir archivo
real, fijar retención de bytes de manera que preserve auditoría y diseñar verificación
incremental/anclajes o backend transaccional equivalente. No se hizo backtesting ni
se afirmó escalabilidad a producción.

Validación B2 final: **67 casos sintéticos aprobados**, además de 52 casos B1
aprobados durante la revisión de compatibilidad. Ocho unitarias web, TypeScript y
build pasan. La suite local completa inicial pasó 271 casos (657,81 s, ejecutada concurrentemente
con E2E); después se agregaron seis casos específicos, incluidos en la validación B2
final. [PR #6](https://github.com/Erixfer98/laliga-modelo/pull/6) publica el recuento
completo y los enlaces CI por commit del cierre de entrega. Un aviso preexistente de
Starlette/TestClient no afecta los resultados.
Las optimizaciones del PR #5 se conservan: `cache_analisis.py`, API, motor estadístico,
liquidación, EV, Kelly, registro Fase 3 y archivos web no se modifican en B2.

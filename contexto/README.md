# Contexto experimental — B1 y B2

B2 añade descubrimiento automático optativo, cliente consciente del plan, evidencia
prospectiva y CLI privado. **No conectado ni activado en producción.**
Guía vigente y matriz de disponibilidad: [FASE5_B2_AVANCE](../docs/FASE5_B2_AVANCE.md).

```bash
python -m contexto.cli_b2 estado
python -m contexto.cli_b2 --db /ruta/absoluta/contexto.sqlite --dry-run catalogo
python -m pytest -q tests/test_contexto_b1.py tests/test_contexto_cliente.py tests/test_contexto_b2.py
```

Los comandos B2 `verificar` y `backup` comprueban fixtures y capturas contextuales.
El CLI B1 siguiente conserva compatibilidad y solo audita los recibos de fixtures.
La clave expuesta previamente debe rotarse antes de operar; no enviarla al chat.
Todos los ejemplos y pruebas de esta entrega son sintéticos o planes sin ejecución.

## Referencia B1 (alcance original)

Infraestructura opt-in. **No está conectada a producción ni captura al importar.**
No contiene analista IA, predicciones alternativas, entrenamiento ni interfaz.

```bash
python -m contexto estado
python -m pytest -q tests/test_contexto_b1.py
python -m contexto verificar --db /ruta/absoluta/contexto-b1.sqlite
python -m contexto backup --db /ruta/absoluta/contexto-b1.sqlite --salida /otra/ruta/copia-nueva.sqlite
```

`estado` muestra presencia, nunca valores de secretos. `b2_ready=false` es deliberado:
una variable no prueba conectividad, licencia, cobertura, durabilidad o restauración.
Los dos últimos comandos requieren un archivo B1 existente; rechazan bases de Fase 3
sin modificarlas. No usar los ejemplos como configuración real del entorno.

## Contratos e identidad

`contratos.py` valida campos exactos, IDs numéricos scoped por proveedor, ligas
internas, UTC con offset, versiones SHA256 y mapeos revisados. No acepta confianza
LLM como identidad. `identidad.normalizar(captura, requested_id, mappings)` deriva el
fixture de bytes del proveedor, exige ID coincidente, consistencia epoch/UTC y dos
participantes distintos. Retorna fixture y mapeos utilizados. No acepta un objeto
fixture construido libremente para archivarlo como procedencia real.

Cada mapeo incluye proveedor, liga/temporada/equipo, nombre interno, intervalo de
vigencia, revisión fechada, revisor y hash de evidencia. La revisión es una afirmación
operativa auditable, no certificación externa: deben revisarse también nombres contra
el catálogo interno y evidencia del organizador antes de habilitar B2. Los nombres
no se adivinan; mapeos ausentes, solapados, no biyectivos o revisados tras captura
fallan cerrados. Nunca asociar a cada combinación manual un partido programado.

`Fixture` identifica el feed; sus recibos declaran `organizer_identity_certified=false`.
Estados desconocidos permanecen desconocidos. Solo `scheduled` y kickoff posterior
al cutoff pasan `apto_para_contexto`; ese resultado no registra ni valida una predicción.
Sede opcional; coordenadas ausentes permanecen nulas. No hay altitud o viajes inventados.

## Conectores implementados, NO verificados con servicios reales

- API-Football: `GET /fixtures?id=...`, clave en header `x-apisports-key`.
- Sportmonks: `GET /v3/football/fixtures/{id}`, includes de participantes/sede/estado.
- Open-Meteo: `GET /v1/forecast`, coordenadas explícitas, fecha UTC futura y unidades.

Usan `requests` existente, proxy/CA heredados y TLS normal. Hosts fijos, solo GET,
redirecciones deshabilitadas, timeout conexión/lectura, máximo 2 MiB descomprimidos.
Sin reintentos automáticos: un 429 se reporta, no consume cuotas ocultamente.
Excepciones de transporte no propagan URLs con tokens. URLs de procedencia excluyen
query/credenciales; los bytes originales de respuesta quedan en almacenamiento privado.

API-Football/Sportmonks sin clave fallan antes de red. Abrir una clase no consulta al
proveedor. B1 no incorpora scheduler, CLI de captura o endpoint público. Clima archiva
respuesta: validar grilla, unidades recibidas, run/disponibilidad y estadio es trabajo
B2; el conector no transforma respuestas en evidencia histórica as-of certificada.
No consultar pasado con forecast para simular pronósticos de entonces.

## Archivo, temporalidad y durabilidad

`Archivo(path_absoluta)` almacena bytes y recibos en SQLite, con triggers append-only,
`BEGIN IMMEDIATE`, `synchronous=FULL`, hashes y cadena. ID idempotente incluye evidencia,
fixture y mapeos: un reintento idéntico conserva el registro original; otra captura
crea otra versión. El registro efectivo se asigna después de obtener el lock y archivar
los bytes. Capturas futuras se rechazan y revierten toda la transacción.

`consultar_asof` usa `registered_at_utc`, no una fecha del cliente: importar ahora una
respuesta supuestamente antigua no permite incorporarla a un cutoff anterior. La
publicación desconocida queda `null/unknown`; no se inventa `available_at_utc`.
Se verifican hashes, cadena, cronología y normalización al consultar. El archive
permite fixtures históricos/postkickoff para auditoría; **no los considera predicciones
prospectivas**. La prohibición de nuevas predicciones tras kickoff sigue en el Registro
Fase 3 intacto. Los tests de éste permanecen presentes.

`backup` usa la API consistente de SQLite, destino nuevo y verificación por reapertura.
Los tests comprueban restauración de datos sintéticos locales. Eso no demuestra que
este entorno tenga persistencia tras reinicio, backups externos o recuperación de desastre.

Para un piloto de un nodo: volumen persistente real, un worker, backup independiente,
referencia de provisión y prueba de restauración en el entorno elegido. Variables:
`KUOTA_CONTEXT_STORAGE_ROOT`, `KUOTA_CONTEXT_BACKUP_ROOT`,
`KUOTA_CONTEXT_DURABILITY_EVIDENCE`. `AlmacenConfigurado` exige directorios absolutos
existentes/separados y rechaza `/workspace`, `/tmp` y `/dev/shm`. Un pase de esa
validación solo prueba configuración de rutas, no durabilidad física. No ofrece
certificación automática ni copia externa programada. No usar disco efímero de
Render free/runner. PostgreSQL/objetos gestionados queda como evolución multiworker,
no implementada ni anunciada como conectada en B1.

SQLite es experimental separado, no migración del Registro Fase 3. Su application_id
protege apertura accidental de otras bases. No modificar triggers/esquema manualmente.
Un administrador capaz de reescribir toda la cadena puede falsificar un archivo local;
los hashes no sustituyen anclajes/firma externa ni exactitud del proveedor.

Límite del piloto: la comprobación completa y consulta as-of recorren el archivo;
la inserción también audita la cadena bajo lock. Coste lineal por operación, no
backend diseñado para grandes volúmenes/múltiples workers. Medir un piloto antes
de ampliar capturas y diseñar índices/auditorías incrementales con garantías
equivalentes. El archivo B1 registra fixtures y sus pruebas de mapeo; el archivo
de noticias/clima enlazado al fixture se incorporará explícitamente en B2.

## Garantías y alcance pendiente

Todo `tests/test_contexto_b1.py` usa datos **SINTÉTICOS**, transporte controlado o archivos
temporales. No es evidencia futbolística ni aceptación de cobertura. Los tests existentes
protegen matemática/registro de Fase 3 y API. B1 no importa entrenamiento, cambia lambdas,
conecta IA ni genera selecciones para boleto. Ajuste contextual no implementado; producción
continúa igual. Pruebas de extracción de rumores/contradicciones y equivalencia del motor
contextual se implementarán con B2/B3, no se declaran completadas aquí.

# Fase 5 — entrega B1 y gate para B2

Estado: infraestructura B1 implementada, **integración operativa pendiente**. B2 detenida.
Base `main`: `768bd375ddfa6e37b35a28c8555768686e455bff`, incluye PR #5.
Rama: `feature/fase-5-inteligencia-contextual`. Sin merge, despliegue, contratación ni activación.

## Código y alcance

| Entrega | Implementado | Conectado a fuente real |
| --- | --- | --- |
| Contratos | Validación estricta de fixture, equipos, UTC, evidencia y versiones | No: sin catálogo/mapeos reales aceptados |
| Identidad | Normalizadores API-Football y Sportmonks, cruce epoch/UTC, mapeos revisados y estados desconocidos | No: respuestas de contrato sintéticas en tests |
| Conectores | GET acotado y permitido por host, autenticación optativa y errores sin tokens; forecast Open-Meteo | No: no se hicieron solicitudes a esos servicios |
| Archivo | SQLite independiente append-only, bytes/hash/cadena, registro efectivo, consulta as-of e idempotencia | Solo probado localmente; ningún volumen durable aprovisionado |
| Recuperación | Backup consistente y verificación por restauración | Solo datos sintéticos; no DR real |
| Producción | Archivos/rutas/boletos y caches PR #5 intactos | Modelo vigente sigue siendo el único |
| B2–B5 | No implementadas en esta entrega | No |

Archivos: `contexto/contratos.py`, `identidad.py`, `conectores.py`, `almacen.py`,
`configuracion.py`, `__main__.py`, README y `tests/test_contexto_b1.py`.
No se añadieron dependencias ni endpoints, cron, migraciones o cambios de despliegue.
[Diseño aprobado](FASE5_ETAPA_A.md) y [uso/contratos](../contexto/README.md).

## Disponibilidad comprobada

Observación del entorno cloud actual: configuración y observaciones vigentes, sin
secretos ni variables de servicio configuradas; red restringida aplicada. No están
permitidos `v3.football.api-sports.io`, `api.sportmonks.com`, `api.open-meteo.com`.
Presencia de las variables conocidas, sin revelar valores:

- `KUOTA_API_FOOTBALL_KEY`: ausente.
- `KUOTA_SPORTMONKS_TOKEN`: ausente.
- Root/backup/evidencia de durabilidad: ausentes.
- PostgreSQL/almacenamiento de objetos: no configurados ni verificados para esta capacidad.

Por tanto, no se afirma cobertura aceptada de seis ligas, identidad certificada del
organizador, captura real, inferencia contextual ni mejora estadística. La lectura de
documentación pública de Etapa A no fue una conexión operativa del conector.
`python -m contexto estado` informa `b2_ready=false`, conexiones no verificadas y
producción contextual deshabilitada. Este gate no se vuelve verde por introducir
variables: requiere aceptación operativa posterior.

## Evidencia temporal y registro

El archivo B1 preserva respuestas y mapeos; no declara predicciones prospectivas.
Su consulta temporal usa registro efectivo: fuentes importadas hoy no aparecen en
un corte de ayer aunque declaren publicación/captura antigua. Conserva `published_at`
desconocido y no certifica timestamps externos. Estado desconocido/aplazado/iniciado
provoca abstención de agenda. Los IDs del feed no prueban oficialidad del organizador.

No se modificó `experimentos/registro.py`. Apertura accidental de una base de Fase 3
con el archivo B1 se rechaza sin modificarla. Sus garantías de idempotencia y rechazo
de nuevas predicciones posteriores al kickoff siguen bajo las pruebas existentes.

## Validación

Validación local del código final:

- **210 pruebas Python aprobadas**, 241,64 s; 52 corresponden a B1. Único aviso:
  deprecación preexistente de Starlette/TestClient, sin fallos.
- **52 pruebas B1** ejecutadas también por separado: 1,08 s.
- **8 unitarias web aprobadas**, TypeScript y build Next.js correctos.
- Comparación de hashes contra main: modelo, probabilidades, API, Kuota, Streamlit,
  caché, registro Fase 3, hook/página de análisis y render.yaml idénticos. No hay
  cambios en el resto de web/experimentos ni dependencias.
- `git diff --check` y compilación del paquete correctos.

Playwright no se repitió localmente: no hay cambios web/API. La CI existente lo
ejecuta sobre el PR y su estado final se documentará en la descripción/checks del
PR; no se presenta como aprobado antes de verificarlo. No se ocultan datos
sintéticos como aceptación real. No se ejecutó backtest contextual sin datos,
coeficientes ni snapshots válidos.

Pruebas nuevas: UTC/offset/DST, IDs y proveedores, temporada, mapeo ausente/ambiguo/no
biyectivo, mismo equipo, timestamp contradictorio, bytes/hashes, evidencia futura,
publicación desconocida, as-of y perturbación futura, idempotencia/concurrencia,
rollback, corrupción, backup/restauración, DB Fase 3 intacta, estados/abstenciones,
redirecciones/429/tamaño/JSON, errores sin secretos e aislamiento de importaciones.

Lambdas y probabilidades contextuales **no existen todavía**: equivalencia del ajuste
cero y entrenamiento temporal se exigirán en B3. B1 no añade ajustes discrecionales.
La equivalencia/regresión actual se acredita manteniendo archivos de producción
idénticos y ejecutando sus pruebas existentes. Rumores/contradicciones de noticias
son pruebas de B2; B1 prueba contradicciones de identidad/fechas/agenda.

## Costes y requisitos para B2

Precios públicos consultados en Etapa A el 11/10/2026, no cotización ni contratación:
[API-Football](https://www.api-football.com/pricing) Pro USD19/mes, 7.500 llamadas/día;
[Sportmonks](https://www.sportmonks.com/football-api/plans-pricing/) Starter EUR29/mes
para cinco ligas más sexta desde EUR4, sujeto a cobertura/extras;
[Open-Meteo](https://open-meteo.com/en/pricing) gratuito solo bajo condiciones no
comerciales y límites; tarifa comercial actual por confirmar.
Infraestructura estimada USD25–80/mes, no proveedor contratado. LLM por elegir/cotizar
más adelante; B1 no llama al LLM ni genera gasto de inferencia. Coste de servicios
contratados por esta entrega: ninguno.

Requisitos verificables antes de iniciar B2:

1. Autorizar/configurar un proveedor de fútbol y credenciales; permitir sus dominios
   por el mecanismo del entorno, sin eludir proxy/TLS o política de red.
2. Aceptar términos de almacenamiento/exhibición/envío a IA y condiciones de clima.
3. Aprovisionar volumen persistente para piloto de un nodo y backup independiente,
   con referencia de provisión y restauración real. Para multiworker, implementar
   explícitamente backend gestionado y pruebas de conformidad antes de operar.
4. Revisar mapeos y fixtures contra catálogo interno y fuentes del organizador;
   muestra de aceptación por liga/temporada (propuesta: al menos 20 por liga).
5. Validar calendario de otras competiciones para descanso real, estadios/coordenadas
   para clima y cobertura/latencia de alineaciones/lesiones.
6. Autorizar operación de captura/scheduler en el entorno durable elegido. Este PR
   no autoriza despliegue. Seleccionar LLM, presupuesto y política de fuentes para B2.

Mientras falten esos requisitos, B1 permanece revisable y B2 bloqueada por disponibilidad.
No se necesita inventar resultados ni obtener una segunda aprobación de arquitectura;
sí acceso y autorización para servicios/capturas que aún no están disponibles.

# B2 — Preparación del worker independiente de Render

## Entrega y límites de autorización

Se prepara `kuota-context-worker`; **no se creó ni desplegó ningún recurso**.
El PR #6 sigue en borrador, rama `feature/fase-5-inteligencia-contextual`.
`kuota-api` (Web Service Free, Oregon, main y auto-deploy según verificación del usuario)
no se administra desde esta propuesta. `render.yaml`, API, modelos, lambdas, matemática,
apuestas, interfaz y dependencias de producción permanecen intactos.

`render-context.yaml` contiene exactamente un servicio experimental: Python,
Oregon, plan `0.5c-512mb`, una instancia, disco de 5 GB en `/var/data`, rama del PR,
auto-deploy off y margen de SIGTERM de 120 s. No contiene secretos, recursos web,
grupos de entorno compartidos, recursos de producción ni acciones de captura en CI.
Campos contrastados con la [referencia oficial de Blueprint](https://render.com/docs/blueprint-spec).
No se validó contra una cuenta de Render ni se aplicó el Blueprint.

**Auto-deploy off no es una autorización ni una garantía de evitar el despliegue inicial.**
Crear un servicio, sincronizar un Blueprint o guardar un disco puede provisionar recursos
facturables e iniciar un deploy. Esta entrega se detiene en código/documentación: no
pulsar los botones finales hasta recibir autorización posterior de creación/despliegue.

## Worker real, deshabilitado inicialmente

Build: `pip install -r requirements-context-worker.txt`.
Start: `python -u -m contexto.worker run`.
No es un comando CLI ejecutado una sola vez. El proceso permanece vivo en un bucle,
publica heartbeat con códigos seguros y espera intervalos configurables. Sin configuración,
no abre el archivo, no lee la clave para un cliente y no hace conexiones externas.

- Dos flags independientes, scheduler y capturas, comienzan en false. Ninguna llave
  ni presencia de volumen los activa. La política por defecto deniega endpoints.
- Lock `contexto.sqlite.worker.lock` durante toda la vida del scheduler: un segundo
  worker del mismo archivo es rechazado. No escalar ni ejecutar otra instancia/cuenta
  consumidora fuera de este archivo. No es un lease distribuido entre discos distintos.
- Lock de operación B2 serializa cliente y backup. Diagnósticos administrativos pueden
  ejecutarse mientras el worker deshabilitado vive, sin iniciar otro scheduler.
- `worker:next_due_utc` se confirma **antes** del intento. Reiniciar preserva agenda,
  restricciones, caché, consumo reservado y recibos; no dispara un ciclo inmediato duplicado.
- Antes de cada ciclo se exporta y prueba restauración externa; después se exportan
  las nuevas capturas y ledger. Si falla el primer respaldo no se consulta fútbol.
  Si falla el segundo, los datos locales siguen confirmados y se conserva la agenda;
  ese ciclo no se declara completado y no se repiten sus consultas inmediatamente.
- SIGTERM/SIGINT solo marcan un booleano sin locks. Esperas se interrumpen con sondeo
  de 100 ms. El worker detiene nuevos trabajos y transmite cancelación a B2/SDK.
  No hace red, SQLite ni `Event.set()` dentro del handler.
- Una petición en vuelo puede terminar o agotar su timeout. No hay garantía de terminar
  toda transferencia dentro de 120 s; un SIGKILL conserva transacciones confirmadas y
  cuenta intentos reservados de forma conservadora. No se publica un ciclo cancelado.
- El ciclo llama funciones Python de `servicio.py`; reutiliza las garantías B2. No llama
  a la web ni ejecuta un subprocess CLI para simular un worker.

Defaults: ciclo cada 86400 s, heartbeat 60 s, ventana UTC de un día. El primer ciclo
habilitado sin agenda previa es inmediato, **solo después de pasar todas las barreras**.
Si una operación falla se espera el próximo intervalo persistido: no hay bucle costoso.
Cambiar flags/intervalos exige reiniciar el proceso experimental mediante un deploy
posterior autorizado. Una agenda anterior se respeta hasta su siguiente fecha.

## Disco y archivo

Después de autorización de almacenamiento, se exige que `/var/data` exista y sea un
mount real. Se rechazan escapes de ruta/symlinks y espacio insuficiente. Estructura:

```text
/var/data/kuota-context/
  contexto.sqlite                 # archivo B1/B2, ledger y estado del worker
  contexto.sqlite.lock            # exclusión por operación
  contexto.sqlite.worker.lock     # exclusión del scheduler
  staging/                        # SOLO temporales de exportación/round-trip
```

Directorios privados 0700 y umask 0077. `/var/data/backup` o `staging` en el mismo disco
**no son respaldo independiente**. La validación B1 de backup local también rechaza
rutas del mismo device. El worker usa R2 como segunda ubicación, no una afirmación de
independencia basada en nombres de carpetas. Montaje y flags no certifican por sí solos
la durabilidad física; debe verificarse el disco en el servicio real.

Límite inicial del archivo: 64 MiB, reserva de espacio para tres copias más 64 MiB.
El disco de 5 GB no implica autorización para ampliar el piloto hasta 5 GB de SQLite.
La auditoría B1/B2 recorre la cadena y puede crecer de forma cuadrática acumulada.
512 MB/0.5 CPU y latencia real deben medirse antes de ampliar volumen o frecuencia.
Al arrancar con respaldo configurado se limpian solo temporales propios `export-*` y
`retention-*` bajo ambos locks; se preservan archivo, evidencia y carpetas ajenas.

Solo lo escrito dentro del mount persiste; el disco está disponible en runtime,
no en build/pre-deploy ni one-off jobs. Se propone diagnóstico desde la Shell/SSH
**de la instancia del worker**, no desde `kuota-api` u otro job. Véase
[discos de Render](https://render.com/docs/disks). No usar un snapshot de disco como
sustituto de la copia consistente y el round-trip de SQLite.

## Respaldo externo privado — preparado, NO conectado

`respaldo.py` implementa S3/R2 con SDK boto3 aislado. Endpoint HTTPS restringido al
formato oficial de cuenta R2, región SDK `auto`, credenciales explícitas backend,
TLS normal, timeouts 5/10 s y un intento SDK. Transferencia sin threads y concurrencia
uno. Se desactivan checksums opcionales del SDK para compatibilidad, pero se exige
SHA256 propio del archivo completo. Referencias:
[boto3 en R2](https://developers.cloudflare.com/r2/examples/aws/boto3/) y
[compatibilidad S3](https://developers.cloudflare.com/r2/api/s3/api/).

Flujo verificable:

1. Contar el intento de exportación en SQLite, incluso si falla o muere el proceso.
2. Copiar con la API `sqlite3.Connection.backup`, nunca copiar a ciegas una base abierta
   ni solo su archivo dejando un WAL pendiente. Auditar cadenas del snapshot.
3. Subir snapshot y manifiesto a prefijo privado dedicado, con directorio único.
4. Descargar ambos a staging, exigir namespace, tamaño, SHA256, manifiesto exacto y
   application_id/schema válidos. Auditar B1/B2 **en modo solo lectura**, que no cambia
   cabeceras al verificar. El ETag o un HTTP 200 aislado no acreditan restauración.
5. Guardar comprobante local de round-trip con fecha efectiva y hash. Aplicar retención
   únicamente después del round-trip. Devolver fallo si retención/exportación no termina.

Retención: 30 días, mínimo tres snapshots completos. Se eliminan solo pares antiguos
manifest/sqlite con formato propio en el namespace dedicado; el actual no se elimina.
No se borran objetos ajenos ni uploads huérfanos/incompletos automáticamente: deben
inventariarse y limpiarse por operación administrativa revisada. No hay garantía de
integridad indefinida de copias antiguas; realizar simulacros periódicos de restauración.
Límite de listado del piloto: 10000 objetos, después bloquea y exige revisión.
Presupuesto separado: ocho intentos de exportación/día UTC, persistente e incluye
fallos; dos exportaciones por ciclo más diagnósticos. No comparte cuota con API-Football.

No hay R2 real, bucket privado comprobado, token, retención del proveedor o restauración
real de desastre verificados en esta ejecución. `PRIVATE_CONFIRMED` es una declaración
operativa, no detección automática de accesos públicos. Al aprovisionar R2 después de
aprobación: bucket dedicado privado, sin r2.dev/dominios públicos, token limitado a sus
objetos (read/write/list/delete), prefijo dedicado y sin logging SDK DEBUG. Evaluar
costes, volumen de copias y política de ciclo de vida con el responsable antes de habilitar.
No se contrata ni se crea nada desde el código.

### Restauración y reconciliación

El comando restaura a una **ruta nueva**, sin reemplazar archivo vivo. Descarga,
verifica hash y cadenas y añade un bloqueo de reconciliación de cuota en la copia
restaurada. `sha256` identifica el snapshot remoto comprobado; `restored_sha256`
identifica la copia operativa después de añadir ese bloqueo. No se alteran recibos
históricos ni timestamps de evidencia.

No se promete exactly-once entre HTTP y SQLite. Un crash entre respuesta y archivo
puede perder esa respuesta; recibos idempotentes y reservas conservadoras protegen
publicación/cuota, no garantizan que jamás se repita un GET. Recuperar un backup antiguo
puede perder intentos recientes: por eso se impide capturar hasta reconciliar saldo con
un `/status` fresco y header de cuota válido. Si el proveedor no entrega ese header,
se mantiene el bloqueo; no se infiere saldo a partir de un flag del operador.

Promoción de una restauración es una acción administrativa **posterior y autorizada**:
parar capturas y scheduler, detener el proceso, conservar copia del archivo actual,
verificar la restauración y cambiar el archivo operativo sin instancias concurrentes.
Reiniciar aún con capturas deshabilitadas, reconciliar cuota y comprobar un nuevo
round-trip antes de solicitar habilitación. El RPO es el último backup exitoso, no cero;
RTO, recuperación con pérdida completa del disco y costes quedan por medir en infraestructura.

## Variables privadas y barreras

Estas variables se configuran **solo en el futuro servicio `kuota-context-worker`**.
No copiar grupos/env de `kuota-api`. No guardar claves en `.env` versionado, YAML,
argumentos, chat, capturas ni logs. Revocar/rotar la clave expuesta previamente.

| Variable | Default / cuándo es necesaria |
|---|---|
| `PYTHON_VERSION` | `3.12.12`, runtime propuesto |
| `KUOTA_CONTEXT_STORAGE_ROOT` | `/var/data/kuota-context` |
| `KUOTA_CONTEXT_STORAGE_AUTHORIZED` | `false`; true solo tras autorizar y verificar disco |
| `KUOTA_CONTEXT_SCHEDULER_ENABLED` | `false` |
| `KUOTA_CONTEXT_CAPTURES_ENABLED` | `false` |
| `KUOTA_CONTEXT_INTERVAL_SECONDS` | `86400`; rango 60–604800 |
| `KUOTA_CONTEXT_HEARTBEAT_SECONDS` | `60`; rango 5–300 |
| `KUOTA_CONTEXT_WINDOW_DAYS` | `1`; rango 1–3 y menor/igual al límite de policy |
| `KUOTA_CONTEXT_MAX_ARCHIVE_MB` | `64`; no ampliar sin piloto de memoria/rendimiento |
| `KUOTA_CONTEXT_POLICY_JSON` | Configuración B2 privada; copiar estructura de `contexto/config/api-football.example.json` |
| `KUOTA_API_FOOTBALL_KEY` | Clave rotada del gestor de secretos, solo para proveedor autorizado |
| `KUOTA_CONTEXT_PROVIDER_DIAGNOSTICS_AUTHORIZED` | `false`; autoriza únicamente `/status` del diagnóstico |
| `KUOTA_CONTEXT_BACKUP_ENABLED` | `false`; true autoriza operaciones externas de respaldo |
| `KUOTA_CONTEXT_R2_PRIVATE_CONFIRMED` | `false`; confirmar configuración privada real antes de true |
| `KUOTA_CONTEXT_R2_ENDPOINT` | Endpoint de la cuenta autorizada; sin query ni credenciales |
| `KUOTA_CONTEXT_R2_BUCKET` | Bucket privado dedicado, no inventado |
| `KUOTA_CONTEXT_R2_ACCESS_KEY_ID` | Secret del token limitado a ese bucket |
| `KUOTA_CONTEXT_R2_SECRET_ACCESS_KEY` | Secret, nunca impreso |
| `KUOTA_CONTEXT_R2_PREFIX` | `kuota-context/b2/`, no raíz de un bucket compartido |
| `KUOTA_CONTEXT_RETENTION_DAYS` | `30`; rango 1–365 |
| `KUOTA_CONTEXT_KEEP_BACKUPS` | `3`; mínimo 2, máximo 100 |
| `KUOTA_CONTEXT_MAX_EXPORTS_PER_DAY` | `8`; rango 1–100, revisar costes antes de cambiar |

En `POLICY_JSON`, `live_authorized`, `credential_rotated`, `network_authorized` y
`restore_verified` deben ser true para capturas; todas comienzan en false. La declaración
`restore_verified` no sustituye el round-trip obligatorio. Para diagnóstico del proveedor
solo se exigen rotación/red, permiso explícito de diagnóstico y clave; no el permiso de
capturar. El comando crea una policy exclusiva `/status`, TTL cero y propósito verification,
con los límites/reserva configurados; no consulta catálogo ni fixtures/alineaciones.
Endpoints y temporadas siguen denegados salvo revisión explícita. Free no habilita
2026 por desplegar un worker: se conservan `subscription_required` y ausencia de fallback.

## Creación manual futura desde Dashboard — NO ejecutar todavía

Preparar estos valores y detenerse antes de guardar/crear recursos facturables.
Tras autorización posterior de creación/despliegue, el responsable puede:

1. Render Dashboard → **New → Background Worker**, conectar `Erixfer98/laliga-modelo`.
   No seleccionar ni editar `kuota-api`, su Environment, Blueprint o disco.
2. Name `kuota-context-worker`; Language/Runtime Python; Branch
   `feature/fase-5-inteligencia-contextual`; Region Oregon. Root Directory vacío
   (raíz del repositorio). Instance Type `0.5c-512mb` (Starter), una instancia.
3. Build Command `pip install -r requirements-context-worker.txt`.
   Start Command `python -u -m contexto.worker run`. No configurar PORT/health endpoint.
4. Advanced → Auto-Deploy **Off**. Shutdown delay 120 s cuando el campo esté disponible.
   Añadir los defaults de `render-context.yaml`, todos los flags de actividad en false.
   No proporcionar credenciales de fútbol/R2 para el primer arranque deshabilitado.
5. En Advanced de la creación añadir el disco: nombre `kuota-context-data`, mount
   `/var/data`, tamaño **5 GB**. Si se añade después, usar **Disk → Add disk** del
   worker; esa acción dispara otro deploy y requiere autorización. No hacerlo en producción.
6. **Punto de aprobación:** confirmar costes y aislamiento antes del botón final
   Deploy/Create Background Worker o Add disk. Esos botones no se pulsaron aquí.
   Auto-Deploy Off controla commits posteriores; no asumir que bloquea la creación inicial.
7. Después del deploy autorizado, comprobar proceso vivo/heartbeat `disabled` y flags
   false. Autorizar almacenamiento separado de capturas, verificar el disco en Dashboard,
   establecer `STORAGE_AUTHORIZED=true` y reiniciar solo el worker conforme al proceso aprobado.
8. Ejecutar diagnóstico local desde su Shell/SSH. Después de autorización externa
   configurar secretos R2/privacidad y probar round-trip real. Después de permiso de proveedor,
   configurar clave rotada y verificar `/status` sin scheduler/capturas.
9. Revisar catálogo/plan y cuotas; completar policy únicamente con IDs/permisos realmente
   verificados. Dejar scheduler/capturas false hasta aprobación adicional de operación.

Alternativa futura Blueprint: indicar explícitamente **Blueprint Path `render-context.yaml`**,
rama experimental, revisar que solo figura el worker y que no aparece `kuota-api` antes de
sincronizar. No utilizar el `render.yaml` de producción ni crear un grupo de entorno compartido.

### Comandos operativos futuros

Sin infraestructura ni secretos, el diagnóstico actual es offline y no crea archivos:

```bash
python -m contexto.worker diagnostico
```

Sobre el worker autorizado y su volumen, con scheduler/capturas **false**:

```bash
# Archivo/cadenas/ledger locales; sin proveedor ni R2:
python -m contexto.worker diagnostico
# Solo /status, usa y registra una solicitud del presupuesto de verificación:
python -m contexto.worker diagnostico --connectivity --execute
# Exporta y descarga copia de nuevo; sin fútbol, requiere respaldo externo autorizado:
python -m contexto.worker diagnostico --external --execute
python -m contexto.worker exportar --execute
# Destino nuevo. El manifiesto es una referencia privada de backup, NO un token:
python -m contexto.worker restaurar --execute --manifest REFERENCIA_DEL_MANIFIESTO --destination /var/data/kuota-context/recovery/contexto-restored.sqlite
# Después de promover/restablecer la copia, con capturas aún false:
python -m contexto.worker diagnostico --connectivity --reconcile-quota --execute
```

Crear previamente el directorio privado de recovery en el volumen aprobado. Exportar/
restaurar sin `--execute` informa dry-run y no hace conexiones. `diagnostico` muestra espacio/tamaño del archivo y presupuesto local (incluidos intentos
reservados). Saldo observado del proveedor puede ser null: no se inventa ni se deduce
de la cuota local. Nunca inicia capturas; sus opciones externas necesitan además flags y secretos autorizados.
No publicar su salida o la evidencia bruta en endpoints públicos. Los únicos logs del
worker son códigos, timestamps y conteos: no imprime informes, cuotas de apuestas,
URLs firmadas, errores SDK crudos ni valores de variables.

## Validación y pendientes

41 pruebas nuevas: SDK Stubber/memoria **SINTÉTICOS**, SIGTERM/SIGINT reales de un proceso
local, exclusión entre procesos, arranque deshabilitado, diagnóstico sin fixtures,
reinicio y reserva tras crash, presupuesto de exportaciones, corrupción, namespace,
retención, copia/restore y bloqueo de cuota tras restauración. La auditoría de restore
usa modo solo lectura y prueba que corresponde al snapshot enviado. Se conservan las
pruebas B1/B2 y matemáticas. Suite local completa inicial: 316 aprobadas (204,91 s); después se añadió el arranque
de mount simulado, el aislamiento del catálogo rechazado y se revisó el diagnóstico de presupuesto. El PR publica la suite
completa final y los enlaces CI por commit. Un aviso Starlette/TestClient preexistente.

**Probado localmente:** comportamiento del software con temporales/mocks y SDK stub;
no conexión R2 ni aceptación de infraestructura Render. **Depende del entorno real:**
mount, cuotas/suscripción, privacidad de bucket, permisos del token, TLS/salida de red,
latencia/memoria, costos, reinicios del servicio y simulacro externo de recuperación.
**Bloqueado hasta autorización:** crear/pagar worker/disco/bucket, desplegar, inyectar
secretos, consultas reales, scheduler y capturas. El resto de B2 mantiene sus limitaciones:
identidad exacta sin alias inventados, cobertura actual no verificada y ningún ajuste de lambdas.

# Fase 3: arquitectura experimental y registro prospectivo

## Aislamiento y secuencia autorizada

El paquete `experimentos/` no es importado por la aplicación, API, web, modelo ni motor de
liquidación. No cambia `K_ENCOGE` global, no parchea funciones de producción y no instala
calibradores. Se ejecuta únicamente mediante CLI. La adopción eventual exige otro cambio revisado.

1. Ejecutar `python -m experimentos --piloto`: mide banco Poisson en 60 partidos de La Liga,
   tiros y goles. No evalúa NB ni representa una comparación predictiva.
2. Ejecutar `python -m experimentos --etapa poisson --procesos 2`: banco causal, selección
   interna y evaluación externa Poisson, comparando actual/sin DC/liga/móvil. Guarda antes
   de NB la dispersión interna y sus hashes.
3. Revisar `seleccion_poisson.json`; solo después ejecutar `--etapa nb`. Cada corte habilita
   NB según sus propios residuos internos anteriores, nunca según el resultado externo.
4. Conservar el modelo vigente; no se selecciona un ganador leyendo scores externos.

Los comandos requieren los gzip verificables de Fase 2, regenerables con
`python -m evaluacion --guardar-predicciones --procesos 2`. Los informes finales, selecciones,
pilotos y hashes se versionan. Los bancos/filas detalladas se excluyen por tamaño. No hay nuevas
dependencias: scipy, numpy, pandas y matplotlib ya forman parte del repositorio.

## Regularización y protocolo

`lambdas.py` implementa media `(sum(w*x)+kappa*mu)/(sum(w)+kappa)` por componente de
ataque/defensa y condición. La referencia de liga positiva es `(sum(w*x)+0.5)/(sum(w)+0.5)`.
El prior Gamma propio se declara antes de ejecutar; no se aprende de meses externos.
Sus pesos fraccionarios no equivalen a una garantía de cobertura posterior. Equipos sin historial
reciben la referencia de liga, sin crear eventos matemáticamente imposibles por conteos cero.

La rejilla contiene kappa 1/3/10/20, xi 0/.005/.01 y ventana completa/180 días. Para goles/1T,
DC rho 0/-.05; dos controles adicionales encogen directamente la lambda actual con kappa 3/10
y exposición mínima de ambas condiciones. Total: 50 candidatos en goles/1T y 26 en las demás métricas.
El banco usa predicciones diarias OOS y Brier OU vectorizado, sin guardar matrices de cada candidato.

Antes de cada mes externo se selecciona usando los tres meses anteriores, con embargo adicional
de un día. Se requieren 100 partidos y dos meses con validación interna. Brier se promedia primero
por las líneas primarias del partido y después por liga; las ligas tienen igual peso en la selección.
El objetivo es OU local para tiros y OU total en las demás métricas. Criterios y desempates son fijos.

Cada mes externo recibe su propia elección interna, congelada durante el mes, aunque sus medias
se actualizan diariamente solo con partidos ya concluidos. Las filas externas no seleccionan su
configuración. Se comparte configuración entre ligas, manteniendo medias de liga independientes.

La dispersión NB se estima sobre conteos con medias internas OOS del candidato seleccionado.
Solo tiros/tiros a puerta/córners/amarillas/rojas son elegibles inicialmente; umbral Pearson medio
1.2 y 30 observaciones positivas. Alpha NB2 en [0,2], mediante likelihood interna; fallback Poisson
si no mejora. No hay búsqueda externa de dispersiones, combinación NB+DC ni selección por ROI.

## Comparabilidad, inferencia y limitaciones

Se reutilizan validación de datos, rejilla fija, objetivos, scores y contratos de cohortes de Fase 2.
Las tablas externas usan los mismos partidos y líneas para todas las referencias y candidatos.
Los fallos parciales abortan; no se permite mejorar scores excluyendo mercados difíciles.
La muestra principal es condicional a la elegibilidad madura del modelo vigente. Los priors para
equipos nuevos se verifican en pruebas; no se atribuye ventaja comparativa a esos equipos, porque
el vigente se abstiene. Su desempeño prospectivo deberá analizarse en una cohorte de cobertura separada.

Las marginales NB son independientes; total usa convolución, no una NB ficticia con parámetros
promediados. Likelihood se calcula sin truncamiento, en logaritmos. Probabilidades OU Poisson se
calculan analíticamente, preservando colas microscópicas que un soporte finito podría convertir en cero.
Se registra cola excluida, soporte, likelihood infinita del vigente, residuos y excedencias 95/99.

Los IC95 son bootstrap semanal descriptivo, con partidos como unidades antes del remuestreo.
Holm ajusta la familia de contrastes primarios entre estrategias y tres referencias; diagnósticos
por líneas/ligas/BTTS/1X2 permanecen exploratorios. Dependencia entre equipos/semanas, pocas temporadas,
prior débil común, independencia local/visitante, definición de tarjetas en MX y modelos separados
para goles total/1T/2T son limitaciones explícitas. No se garantiza coherencia conjunta entre períodos.

Julio–septiembre ya se examinó en Fase 2: ningún bloque de los archivos actuales se declara holdout
independiente nuevo. La evidencia independiente requiere cerrar el protocolo y registrar predicciones
para partidos futuros. No se ha capturado todavía esa evidencia. No hay cuotas reales verificables.

## Registro prospectivo implementado

CLI opt-in:

```bash
python -m experimentos.registro --db work/prospectivo.sqlite \
  --entrada work/prediccion.json --snapshot work/datos-capturados.csv
```

Contrato JSON de predicción:

| Campo | Regla |
|---|---|
| fixture_id, liga | Identificación oficial estable; no reutilizar el hash basado en fecha como ID oficial |
| kickoff_utc, generated_at_utc | Zona obligatoria; normalización UTC; generación antes del kickoff |
| configuracion | Parámetros y reglas de selección originales, JSON explícito no vacío |
| modelo_version, codigo_commit | Versión experimental y SHA de commit de 40 caracteres |
| metrica, kind, lado, linea | Mercado OU entero/media línea, BTTS o 1X2; identidad explícita |
| lambdas | Dos medias positivas finitas, originales |
| probabilidades | Vector original p0/p1/p2; suma uno; sin push en medias líneas/BTTS |
| alcance, experimental | `regulation`, `true`; no activar modelos de producción |
| datos | Lista de snapshots, fuente, SHA256, captured_at_utc, available_at_utc, as_of_utc |

Los hashes se comparan con los archivos suministrados; disponibilidad/captura deben ser anteriores
a la generación. La hora efectiva de registro se obtiene del sistema y se comprueba dentro de la
transacción, antes del kickoff. Una transacción `BEGIN IMMEDIATE` serializa inserciones concurrentes.
Las tablas rechazan UPDATE/DELETE mediante triggers. El ID de contenido hace idempotentes los reintentos.
Una cadena SHA256 enlaza los registros; `Registro.verificar()` detecta alteraciones ordinarias.

Esta cadena no es una firma de un tercero y el administrador de la base puede modificar su esquema.
Los timestamps del proveedor son declaraciones conservadas, no prueba externa de disponibilidad.
El diseño no simula captura histórica ni hace pasar registros de pruebas por predicciones reales.

## Extensión prevista para cuotas y resultados

El registro actual implementa predicciones y procedencia. La captura de apuestas no se activa.
Entidades futuras separadas, enlazadas por prediction_id/fixture oficial:

- Captura de cuota: bookmaker, selección, cuota decimal, captured_at UTC y reglas; múltiples capturas
  sin sobrescribir. Cierre registrado por separado, con el mismo mercado y reglas.
- Resultado: conteos oficiales, alcance 90 minutos, fuente, publicación, estado provisional/final y revisión.
- Liquidación: referencia al resultado y cuota, acierto/push/fallo/anulación y versión de reglas Fase 1.

Registrar cotizaciones reales no autoriza apostar. Sin datos verificables no se calcula ROI, CLV,
yield, drawdown ni rentabilidad. El registro experimental no añade endpoints ni tareas automáticas a producción.

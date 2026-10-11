# Dictamen técnico final del PR #3

**Aprobable para merge como infraestructura experimental de Fase 3.** El modelo vigente permanece
intacto. Esta aprobación no autoriza activar candidatos, calibradores, tareas prospectivas en
producción ni desplegar. No se ejecutó merge ni despliegue.

## Selección temporal anidada

No se encontró uso del mes externo para seleccionar parámetros o decidir NB. Para un mes externo M,
la validación interna comprende `[inicio(M−3), inicio(M)−1 día)`: el día inmediatamente anterior
al inicio queda excluido por embargo. Cada predicción interna usa historial con `fecha < fecha_predicción`;
ni los resultados de ese día ni los posteriores alimentan sus lambdas. Las medias de liga, exposición,
encogimiento y recencia se calculan con ese historial; no hay normalización aprendida con el histórico completo.
La variante directa reutiliza lambdas causales de Fase 2, con procedencia y hashes comprobados por el CLI.

El candidato se elige por Brier interno macro por liga, sobre la misma cohorte por candidato. El residuo
Pearson de cada partido es `[(y_local−λ_local)²/λ_local + (y_visitante−λ_visitante)²/λ_visitante]/2`;
su media y el número de positivos se calculan exclusivamente con las predicciones internas del candidato
seleccionado. NB solo se habilita en métricas elegibles con Pearson >1,2 y al menos 30 positivos. Su α
se ajusta por likelihood NB2 con esas mismas lambdas y observaciones internas. No se ajusta a residuos
externos ni a resultados del mes que se evaluará.

Las lambdas externas se actualizan diariamente con partidos anteriores a ese día, incluidos partidos
anteriores del propio mes externo. Eso representa información disponible al predecir y no constituye
selección con resultados futuros. Los hiperparámetros y α quedan seleccionados antes de ese mes.
La selección de meses posteriores puede usar observaciones ya pasadas de meses externos anteriores:
es validación temporal móvil, no un único holdout congelado.

Se añadió una auditoría reproducible (`python -m experimentos.auditoria`) del banco real:

- **72 cortes**, ocho métricas por nueve meses; **28 cortes NB habilitados**.
- Perturbación de resultados, lambdas y Brier desde el día de embargo en adelante: selección,
  parámetros, residuos, positivos, gate y α exactamente iguales para cada corte.
- Banco truncado al pasado, conservando solo filas externas para enumerar el corte: mismos ajustes.
- Ajustes recalculados idénticos a los artefactos persistidos.

La evidencia con hashes está en [auditoria_temporal_final.json](fase3/auditoria_temporal_final.json).
Las pruebas automatizadas cubren además perturbación del CSV crudo, recomputación de Fase 2 y del banco,
selección NB y predicciones externas anteriores a la perturbación, incluyendo probabilidades y likelihood.

**Límite:** el CSV retrospectivo no conserva disponibilidad histórica ni revisiones de proveedor.
Se demuestra causalidad por fecha bajo ese supuesto, no replay histórico as-of certificado. El histórico
ya se examinó en Fase 2; sus resultados siguen siendo exploratorios, fuera de muestra por corte pero
sin constituir evidencia independiente. No se eligió un ganador para producción con el período externo.

## Registro efectivo y procedencia

Se corrigió la ausencia de conservación de evidencia: antes se cotejaban hashes de archivos, pero no
se archivaban sus bytes. Ahora los snapshots originales se conservan en SQLite, en la misma transacción
que la predicción, con triggers que rechazan UPDATE/DELETE. Al verificar o consultar se recomputan los
hashes, se comprueba la cadena y se valida la cronología. La falta o alteración de un snapshot invalida
la consulta; las bases antiguas sin evidencia archivada fallan cerradas y no se completan retroactivamente.

`generated_at_utc` es una declaración del generador. `registered_at_utc` lo asigna el reloj del servidor
tras obtener el lock y archivar los snapshots, dentro de la transacción. No se admite ese campo en el
payload del cliente. `Registro.consultar(id)` y el CLI `--recibo` muestran ambas horas. La elegibilidad
local exige `generated_at_utc <= registered_at_utc < kickoff_utc`, integridad y evidencia archivada;
antidatar la generación no permite registrar una predicción nueva después del kickoff.

Un reintento idéntico, incluso después del inicio, devuelve el ID original y conserva su hora efectiva:
no crea ni retrodata otro registro. Una predicción diferente se rechaza exactamente en el kickoff o
posteriormente, y se revierte también el archivo de nuevos snapshots. Se probaron inserciones concurrentes,
la normalización UTC, archivos de entrada borrados, evidencias alteradas y cruce del kickoff mientras
se procesa una inserción.

El recibo distingue verificación de bytes de certificación externa:
`disponibilidad_proveedor_certificada=false`. La evidencia acredita el registro local bajo confianza
en su reloj y base, no identidad del proveedor ni timestamps históricos declarados. Antes de una
confirmación independiente hay que verificar fixture y kickoff oficiales, congelar protocolo y
commit/configuración y conservar la procedencia de la captura. No se presentan fixtures simulados
como evidencia futura real. Una cadena local no sustituye firmas o anclajes de terceros.

## Resultados y validación

Las correcciones afectan al registro y a la auditoría, no al motor de inferencia ni al protocolo
estadístico. Se regeneraron los reportes desde inferencia con hashes verificados. Banco, selecciones,
predicciones, conteos y todos los CSV/figuras estadísticos conservan sus hashes: Brier, Log Loss,
calibración, intervalos, resultados por mercado/liga y conclusiones permanecen idénticos.
La comprobación está en [invariancia_resultados_final.json](fase3/invariancia_resultados_final.json).
El manifest se actualizó para reflejar el código actual y la nueva regeneración del informe.

Tiros local sigue siendo el único mercado que cumple todos los criterios exploratorios frente a las
tres referencias: Brier actual **0,162577**, Poisson regularizado **0,157065**, NB condicional **0,155858**;
Log Loss **0,544519 → 0,518226 / 0,508369**. NB no es superior de forma consistente en todos los mercados.
Se conserva el modelo vigente y no se infiere rentabilidad a partir de precisión predictiva.

**135 pruebas Python** (30 casos de Fase 3), **3 pruebas web**, comprobación TypeScript y build Next.js
aprobados. El único aviso Python es la deprecación preexistente de Starlette/TestClient. La auditoría
real de los 72 cortes y la regeneración de informes también terminaron correctamente.

Para reproducir las comprobaciones adicionales tras generar el banco y la inferencia:

```bash
python -m experimentos.auditoria
python -m experimentos --etapa nb --reusar-inferencia
python -m pytest -q
cd web
npm test
npx tsc --noEmit --incremental false
npm run build
```

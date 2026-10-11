# Conclusiones de Fase 3

Se conserva el modelo vigente en producción. Poisson regularizado y NB condicional son candidatos
experimentales para validación prospectiva, especialmente en **tiros del local**. Ninguno se activa
por este PR. La evidencia independiente permanece pendiente y no se afirma rentabilidad.

Las configuraciones se eligieron en ventanas internas anteriores a cada mes externo. Las tablas
externas describen esas estrategias; no se seleccionó un ganador leyendo los resultados externos.

## Muestra y procedimiento

- 2.197 partidos históricos; 1.406 partidos externos maduros, 33 bloques semanales y nueve cortes
  mensuales por métrica. Períodos sin validación interna suficiente se omiten para todos los modelos.
- 395.520 predicciones de configuración/partido/métrica en el banco Poisson causal.
- 72 selecciones internas; 28 cortes habilitan estimación NB tras medir dispersión interna anterior.
- 1.505.826 filas de mercados entre siete modelos, con claves y objetivos idénticos. Las filas no
  equivalen a partidos independientes. Referencias actual/sin DC/liga/móvil permanecen presentes.

## Interpretación y recomendaciones

La regularización mejora los mercados primarios frente al actual en las seis ligas. Sin embargo,
mejorar al actual no basta: la referencia de liga sigue siendo especialmente competitiva en goles
 y córners. Solo tiros del local satisface todos los umbrales exploratorios frente a actual/liga/móvil,
con control Holm de 42 contrastes y estabilidad temporal/geográfica. No es evidencia independiente.

En tiros del local, Poisson reduce Brier **0,162577→0,157065** y Log Loss **0,544519→0,518226**.
NB condicional obtiene Brier **0,155858** y Log Loss **0,508369**. ECE descriptivo baja de 0,048947
a 0,033438 y 0,021970 respectivamente; sus bins contienen selecciones correlacionadas.

El efecto incremental de NB sobre las mismas lambdas es favorable en tiros del local: mejora Brier
≈0,001207, IC95 semanal descriptivo [0,000273; 0,002098], y Log Loss ≈0,009858. Estos contrastes
incrementales son diagnósticos, sin ajuste simultáneo; no seleccionan ganadores ni autorizan adopción.
NB mejora al Poisson regularizado en cinco ligas y empeora ligeramente en Premier. En córners,
tiros a puerta y rojas empeora ligeramente Brier frente a Poisson regularizado; sus IC incluyen cero.
En amarillas y goles no se habilita: coincide por fallback, no por equivalencia demostrada de NB.

La ablación DC mantiene las lambdas seleccionadas. Su efecto OU total es prácticamente nulo en
goles y ligeramente desfavorable en 1T, con IC que incluyen cero. No hay base para cambiar todavía
el rho de producción. BTTS/1X2 y lados se conservan como diagnósticos en `dixon_coles.csv`.

Los candidatos tienen cero observaciones conjuntas de probabilidad cero en la muestra evaluada.
El actual conserva 140 observaciones fixture/métrica con likelihood conjunta infinita: no son
necesariamente 140 partidos distintos. No se ocultan scores infinitos ni se eliminan esas filas.
La positividad procede de priors/encogimiento, no de epsilon aplicado a probabilidades observadas.
No garantiza por sí sola calibración ni superioridad para equipos nuevos; su comparación de cobertura
requiere una cohorte separada porque el actual se abstiene.

## Rendimiento y registro

El piloto Poisson midió banco vectorizado y probabilidades completas en 60 partidos. La ejecución
Poisson definitiva tardó aproximadamente **332 segundos**; NB con piloto adicional y reutilización
del banco, **294 segundos**. El piloto NB procesó 3.840 registros de conteos en unos 19 segundos,
muy por debajo del presupuesto de 30 minutos para la inferencia masiva. Son mediciones locales.
Regenerar análisis desde inferencia verificada tarda unos 70 segundos.

Se implementó registro opt-in SQLite append-only de predicciones, configuración, commit, lambdas,
probabilidades originales, UTC y procedencia con hashes y bytes originales archivados.
El recibo distingue generación declarada de registro efectivo del servidor; la elegibilidad
requiere registro anterior al kickoff y evidencia archivada íntegra. Rechaza datos
posteriores a la generación y registro tras el kickoff; normaliza UTC, serializa inserciones,
hace idempotentes reintentos y detecta alteraciones ordinarias mediante cadena SHA256.
No añade endpoints, pantallas, cron ni cambios de funcionamiento en producción.

La cadena no sustituye firmas externas ni certifica timestamps declarados por proveedores.
No se han capturado todavía predicciones reales futuras o cuotas. La extensión prevista para cuotas,
resultados y liquidaciones está en [arquitectura y registro](FASE3_DISENO_Y_REGISTRO.md).

La siguiente evaluación debe congelar commit/configuración y registrar predicciones antes del kickoff.
Los hiperparámetros no se elegirán con ese período independiente. Julio–septiembre ya fue analizado
en Fase 2: no constituye un holdout inédito. No se calculan ROI, CLV ni rentabilidad sin cuotas reales.

## Validación y reproducción

**135 pruebas Python**, incluyendo 30 casos de Fase 3, y **3 pruebas web** aprobadas. TypeScript y
build Next.js correctos. Incluyen oráculos Poisson/DC/NB, causalidad, selección anidada, gates de NB,
cohortes, Holm, infinitos, CLI/caché, registro inmutable, UTC, inserción tardía e importaciones de producción.
Un aviso preexistente Starlette/TestClient, sin fallos.

```bash
python -m experimentos --piloto
python -m experimentos --etapa poisson --procesos 2
python -m experimentos --etapa nb --procesos 2
python -m experimentos --etapa nb --reusar-inferencia
```

Se requiere el caché verificable Fase 2. El protocolo, parámetros y hashes se versionan; los gzip
son regenerables. Los datos, el motor de liquidación, modelo vigente, API y web no cambian.

[Informe completo y figuras](fase3/REPORTE.md) · [Resultados por liga](fase3/ligas.csv) ·
[Por línea](fase3/lineas.csv) · [Intervalos](fase3/intervalos.csv).

## Tablas resumidas

| mercado | candidato | brier_actual | brier_candidato | brier_liga | brier_movil | logloss_actual | logloss_candidato | evidencia |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| amarillas OU total | poisson_regularizado | 0.219057 | 0.206630 | 0.208256 | 0.213052 | 0.695507 | 0.659066 | evidencia insuficiente |
| amarillas OU total | nb_condicional | 0.219057 | 0.206630 | 0.208256 | 0.213052 | 0.695507 | 0.659066 | evidencia insuficiente |
| corners OU total | poisson_regularizado | 0.220986 | 0.205837 | 0.205423 | 0.223027 | 0.705730 | 0.656017 | evidencia insuficiente |
| corners OU total | nb_condicional | 0.220986 | 0.206086 | 0.205423 | 0.223027 | 0.705730 | 0.655732 | evidencia insuficiente |
| goles OU total | poisson_regularizado | 0.217645 | 0.203706 | 0.203575 | 0.211867 | 0.696424 | 0.654841 | evidencia insuficiente |
| goles OU total | nb_condicional | 0.217645 | 0.203706 | 0.203575 | 0.211867 | 0.696424 | 0.654841 | evidencia insuficiente |
| goles_1t OU total | poisson_regularizado | 0.243088 | 0.225504 | 0.224220 | 0.233355 | 0.775399 | 0.717127 | evidencia insuficiente |
| goles_1t OU total | nb_condicional | 0.243088 | 0.225504 | 0.224220 | 0.233355 | 0.775399 | 0.717127 | evidencia insuficiente |
| goles_2t OU total | poisson_regularizado | 0.256516 | 0.238976 | 0.237833 | 0.249044 | ∞ | 0.753378 | evidencia insuficiente |
| goles_2t OU total | nb_condicional | 0.256516 | 0.238976 | 0.237833 | 0.249044 | ∞ | 0.753378 | evidencia insuficiente |
| rojas OU total | poisson_regularizado | 0.121980 | 0.108652 | 0.108772 | 0.115139 | ∞ | 0.381015 | evidencia insuficiente |
| rojas OU total | nb_condicional | 0.121980 | 0.108771 | 0.108772 | 0.115139 | ∞ | 0.381388 | evidencia insuficiente |
| tiros OU local | poisson_regularizado | 0.162577 | 0.157065 | 0.174631 | 0.167159 | 0.544519 | 0.518226 | exploratoria favorable |
| tiros OU local | nb_condicional | 0.162577 | 0.155858 | 0.174631 | 0.167159 | 0.544519 | 0.508369 | exploratoria favorable |
| tiros_a_puerta OU total | poisson_regularizado | 0.178732 | 0.168553 | 0.169440 | 0.175041 | 0.583062 | 0.550062 | evidencia insuficiente |
| tiros_a_puerta OU total | nb_condicional | 0.178732 | 0.168682 | 0.169440 | 0.175041 | 0.583062 | 0.550595 | evidencia insuficiente |

Tiros del local por liga, sobre idénticos partidos:

| competicion | actual | liga | movil_10 | poisson_regularizado | nb_condicional |
| --- | --- | --- | --- | --- | --- |
| bundesliga | 0.157376 | 0.170725 | 0.155849 | 0.154201 | 0.153797 |
| laliga | 0.164499 | 0.180359 | 0.171387 | 0.161172 | 0.159189 |
| ligamx | 0.166172 | 0.178374 | 0.172567 | 0.160360 | 0.158458 |
| ligue1 | 0.172090 | 0.173801 | 0.174845 | 0.162581 | 0.160537 |
| premier | 0.160175 | 0.162995 | 0.164932 | 0.151149 | 0.151958 |
| seriea | 0.158177 | 0.182194 | 0.165417 | 0.155273 | 0.153191 |

Revisión final: [dictamen y pruebas de perturbación](REVISION_FINAL_FASE3.md). Las selecciones
y conclusiones estadísticas permanecen iguales tras revisar los 72 cortes temporales.

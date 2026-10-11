# Fase 1: coherencia matemática y seguridad de cálculo

Implementación sobre `fix/probabilidades-kelly-auditoria`, cuyo punto de partida es
`941d2de` (bloqueo parcial de Kelly). Comparación con `main` en `46bd234`.
Las fuentes y CSV existentes no se modifican. Se mantienen Python, FastAPI,
Streamlit y Next.js. No se fusiona, no se despliega y no se cambian configuraciones
ni secretos de producción.

## Errores corregidos

- El bloqueo parcial de Kelly conservaba probabilidades y EV incorrectos para
  combinadas correlacionadas. Ahora existe un contrato completo de disponibilidad.
- Las matrices de tamaño fijo descartaban hasta el 56,29% de masa en los casos
  auditados; sus marginales no concordaban con los mercados individuales.
- Los cuatro vértices de un rectángulo no bastan para mercados no monótonos,
  como empate. El punto central podía quedar fuera del rango mostrado.
- Solo se propagaba incertidumbre ofensiva; faltaba la defensa del rival.
- Un promedio cero generaba un rango `[0, 0]` y divisiones por cero cuando toda
  la liga carecía de eventos de una métrica.
- Under entero se calculaba como `1 - Over`, incluyendo devoluciones como aciertos.
- Una probabilidad cero producía cuota justa infinita y JSON no serializable.
- El cliente enviaba probabilidades aceptadas por el servidor y Next.js duplicaba
  la multiplicación incorrecta en el resumen local.

## Distribución compartida y error numérico

`probabilidades.py` genera una matriz vectorizada Poisson. Para cada intensidad
elige el menor límite (con mínimo visual de 6) que deja una cola marginal inferior
aproximadamente a `5e-13`. El soporte compartido usa el mayor límite necesario
para el centro y los parámetros de sensibilidad. `K_MAX` es ahora un mínimo
compatible, nunca el máximo que trunca una distribución.

La masa excluida se calcula con funciones de supervivencia:

```
e = P(X > k) + P(Y > k) - P(X > k) P(Y > k)
M[x,y] = Poisson(x; λl) Poisson(y; λv) τ(x,y) / masa_retenida
```

Se exige `e <= 1e-12`. La normalización condiciona explícitamente al soporte.
La discrepancia absoluta con una probabilidad de evento de la distribución
infinita queda acotada por esa masa, salvo redondeo de coma flotante. No se
promete error relativo pequeño para sucesos de probabilidad extremadamente baja.
La masa, tolerancia, límite, normalización y versión se exponen en la API.

Dixon–Coles conserva sus cuatro ajustes y su suma neta nula. Se comprueba que
**todos** los multiplicadores sean no negativos. Una intensidad central inválida
produce un error explícito, sin recortar probabilidades negativas ni alterar rho.
Con `rho=-0.05`, la sensibilidad se intersecta con el dominio admisible
`λl <= 20`, `λv <= 20`; el dominio aparece en la trazabilidad.

No cambian `XI=0.005`, `RHO=-0.05` ni `K_ENCOGE=0`. No se introduce otra
familia de distribuciones ni una recalibración predictiva.

Todos los mercados, incluidos individuales, salen de esa matriz. Los gráficos
pueden mostrar solo una parte de ella: indican masa visible y conservan sus
probabilidades originales, sin normalizar el recorte visual. Se marca la
igualdad de una línea entera como devolución. El backtest existente también
consume las marginales compartidas; sus líneas generadas siguen siendo medias.

Se rechazan conteos negativos, fraccionarios o infinitos y pesos inválidos antes
de calcular fuerzas. Los datos ausentes siguen excluyéndose por pares de columnas;
no se añade un método de imputación. Si la media de liga es cero, las fuerzas usan
una referencia neutral y la intensidad central es cero, sin `0/0`.

## Sensibilidad y trazabilidad

Se conservan promedios ponderados, tamaño efectivo, desviación y multiplicador t
como **heurística**. Se calculan tanto para producción como para concesión.
Con referencia de liga fija `μ`, la intensidad es:

```
λl = media_ataque_local_casa × media_defensa_visitante_fuera / μcasa
λv = media_ataque_visitante_fuera × media_defensa_local_casa / μfuera
```

Los rangos de ambos factores no negativos se propagan mediante productos de sus
límites. No se añade un margen arbitrario a las probabilidades. El parámetro
central es siempre un escenario real evaluado, además de una rejilla `7 × 7`
interior del rectángulo (hasta 50 puntos únicos). Para cada evento se muestran
mínimo y máximo de **esos escenarios**. La misma pareja de parámetros produce
acierto, fallo y devolución de cada escenario.

Para un promedio observado de cero se usa `-log(0.1)/n_ef` como intensidad superior
de sensibilidad: proviene de invertir la probabilidad Poisson de observar cero
sucesos. **No** es un intervalo validado para observaciones ponderadas, dependientes
ni para la intensidad compuesta. Sin historial se utiliza la referencia de liga,
como ya hace el estimador central. Si toda la liga tiene cero eventos, se usa su
exposición efectiva agregada para una referencia de sensibilidad no nula.

La API expone los componentes ofensivo y defensivo, sus medias y exposiciones,
la referencia de liga, intensidades centrales, límites, método y
`cobertura_validada=false`. Los escenarios pueden ser muy amplios: por ejemplo,
si ambos límites inferiores incluyen cero, el empate puede alcanzar probabilidad
1 en el escenario `(0,0)`. Es una consecuencia del método de sensibilidad, no
una promesa de precisión.

**Limitación:** la rejilla no certifica los extremos globales de un mercado no
monótono. No incorpora covarianzas entre estimadores ni incertidumbre del promedio
de liga. Se eliminan las afirmaciones de cobertura del 80%; falta validar cobertura
con remuestreo o evaluación temporal antes de usar ese lenguaje.

## Combinadas, liquidación y Kelly

Cada selección nueva guarda una identidad verificable:
`liga / local / visitante / métrica / regla canónica / versión`.
El servidor reconstruye el modelo desde el CSV vigente y nunca utiliza las
probabilidades, rangos o etiquetas enviados por el cliente para recomendar stake.
El resumen incluye la revisión del CSV e intensidades utilizadas. Las cifras de
las patas guardadas se etiquetan «al agregar»; el boleto se recalcula con los datos
vigentes y puede diferir si se actualizó el CSV. Las selecciones
antiguas sin identidad deben volver a agregarse.

| Caso | Probabilidad y EV | Kelly |
|---|---|---|
| Una selección válida | Matriz y liquidación explícita | Distribución de retornos |
| Mismo partido y misma métrica | Intersección en la matriz compartida | Mínimo de escenarios calculados |
| Mismo partido y distintas métricas | `null`: falta distribución conjunta | `null`, sin opciones |
| Duplicados canónicos | `null`: boleto inválido | `null`, sin opciones |
| Selecciones sin ningún retorno beneficioso posible | Probabilidad de acierto conjunto 0 y EV de liquidación | Deshabilitado |
| Sin acierto total posible, pero con pagos por pushes | Probabilidad de acierto conjunto 0 y EV de liquidación | Calculado sobre retornos parciales |
| Partidos distintos | Producto **entre grupos de partidos**, con hipótesis explícita de independencia | Escenarios de sensibilidad |
| Selección antigua o sin identidad | `null`, se solicita volver a agregarla | Deshabilitado |

`prob` del boleto significa **todas las selecciones acertadas**; no incluye
selecciones devueltas. `push` del boleto es la devolución íntegra: retorno bruto 1.
Los retornos parciales se conservan en `liquidaciones` y se usan para EV/Kelly.

Para un Over/Under de línea L:

```
Over: acierto si cantidad > L; Under: acierto si cantidad < L
Devolución: cantidad = L; fallo: complemento de acierto y devolución
p_acierto + p_fallo + p_devolución = 1
EV_individual = cuota × p_acierto + p_devolución - 1
cuota_justa = (1 - p_devolución) / p_acierto
```

Con probabilidad de acierto cero o cuota fuera del rango finito representable,
la cuota justa es `null`. Over y Under de media línea son complementos; con línea
entera se necesita sumar el push. El historial cuenta exclusivamente desigualdades
estrictas como acierto y muestra las devoluciones aparte. La calificación sigue
usando la frecuencia de aciertos por partido, sin convertir pushes en aciertos.

La liquidación de una combinada tradicional se calcula por resultado de la matriz:
una pata perdida devuelve 0, una devuelta aporta factor 1 y una acertada aporta
su cuota. En grupos independientes se combinan esas distribuciones de retornos.
Por tanto:

```
EV = Σr P(R=r) (r-1)
Kelly = argmax[0 <= f < 1] Σr P(R=r) log(1+f(r-1))
```

Si el EV no es positivo, Kelly es 0. Para retornos generales se resuelve la
derivada con tolerancia relativa de precisión máquina, sin tolerancia absoluta
que borre fracciones positivas pequeñas. Para una sola cuota ganadora y
retornos 0/1 se usa directamente la solución cerrada, limitada a [0,1−10⁻¹⁰].
Para una apuesta con push la expresión analítica de comprobación es
`f = (b·p_acierto - p_fallo)/(b·(p_acierto+p_fallo))`, con `b=cuota-1`.
Se devuelve el menor Kelly de los escenarios de sensibilidad evaluados.
Para boletos binarios sin pushes el mínimo se obtiene directamente de la menor
probabilidad conjunta; no hay expansión combinatoria innecesaria.

Se admiten Over/Under enteros y medios, resultados, doble oportunidad y BTTS.
Cuartos de línea, hándicaps y reglas adicionales se rechazan explícitamente.
Para boletos con devoluciones parciales no hay una cuota justa única deducible
solo de la probabilidad de acierto completo; se devuelve `null`, excepto para
una selección individual.

**Precio y reglas de la casa:** EV y Kelly asumen producto de cuotas de patas
ganadoras y eliminación de pushes. No son aplicables a precios especiales de
same-game parlays o devoluciones diferentes. Se muestra esta condición en el
boleto. La app no verifica que una casa acepte la combinación ni sus cuotas.
La identidad es un escenario de equipos local/visitante, no un ID de un partido
calendarizado; la arquitectura actual no representa distintas fechas del mismo
emparejamiento.

## Contratos de interfaz y límites operativos

- FastAPI devuelve errores 422 para reglas y parámetros no implementados.
  `null` representa no disponibilidad; `sin_valor` representa un Kelly calculado
  no positivo. No se confunden ambos estados.
- Streamlit y Next.js muestran «No disponible» y no renderizan stake cuando falta
  Kelly. No se emite `NaN` ni `Infinity` en JSON.
- Next.js guarda la selección canónica, elimina el cálculo local de probabilidades
  de combinadas y oculta resultados que pertenecen a otra combinación/banca mientras
  llega una respuesta nueva.
- Límite de soporte 256, líneas hasta 100, hasta 12 patas, hasta 100.000 retornos
  únicos y 4.096 combinaciones de escenarios con pushes. Si no se puede enumerar
  la sensibilidad de pushes, EV central sigue disponible, pero Kelly y extremos
  de EV quedan deshabilitados. No se sustituye silenciosamente por independencia.
- Caché de modelos de boleto de 8 entradas, invalidada por modificación de CSV.
  La rejilla aumenta el coste respecto de los cuatro vértices anteriores. El coste
  matricial es aproximadamente O(50·k²), además del cálculo de fuerzas; no se ha
  realizado una prueba de carga ni se garantizan latencias de producción.

## Comparación reproducida

Cálculos sobre los CSV existentes en el commit base; cifras completas y lambdas
están en `docs/comparacion_fase1.json`. Las intensidades centrales no cambian.

| Caso | Antes | Después | Interpretación |
|---|---:|---:|---|
| Hoffenheim–Elversberg, empate | 15,2554%, rango 2,1786–8,3531% | 15,2217%, rango 0,0058–100% | Cola corregida; ataque/defensa e interiores corrigen el rango |
| Barcelona–Racing, Barcelona Over 18.5 córners | Mercado 56,4026%, matriz 29,0771% | Ambos 56,4026% | Se elimina la contradicción entre marginal y matriz |
| Bayern–Elversberg, Total Over 46.5 tiros | 15,4684% | 49,2607% | Se descartaba 49,6970% de masa |
| Coventry–Ipswich, Total Over 0.5 rojas | 98,4879% | 99,3390% | Se descartaba 56,2874% de masa |
| Barcelona–Madrid, Barcelona Over 0.5 rojas | 0%, rango λ `[0,0]` | 0%, rango λ `[0,0.144292]` | Cero observado no significa incertidumbre nula |
| Madrid–Barcelona, Under 3.0 | Acierto supuesto 44,7981% | Acierto 24,9083%; push 19,8891% | La igualdad ya no se trata como acierto |
| Under 3.0 anterior, cuota 3 | EV +0,34394 | EV −0,05386 | EV corregido por liquidación y cola |

Los nuevos soportes para estos casos son 39, 88, 147, 67 y 8, respectivamente.
La masa excluida central es inferior a `1e-12`; en varios casos es mucho menor
porque el soporte también cubre las intensidades superiores de sensibilidad.

No se afirma mejora predictiva, calibración ni rentabilidad. No se vuelve a
publicar un backtest completo ni se sustituye el reporte histórico existente.
El smoke test del backtest comprueba integración y ausencia de probabilidades
no finitas en un conjunto pequeño; no mide capacidad predictiva.

## Validación y reproducción

```
python -m pip install -r requirements-dev.txt
python -m pytest -q
cd web
npm ci
npm test
npx tsc --noEmit --incremental false
npm run build
```

Las pruebas cubren los cinco emparejamientos de la auditoría, un fixture numérico
inmutable del empate, Under 3 con push, cuotas de probabilidad cero y microscópica,
combinadas exactas/dependientes/excluyentes, duplicados canónicos, datos inválidos,
propiedades aleatorias de complementos y normalización, JSON finito, FastAPI,
pantallas reales de Streamlit sin red y un backtest reducido.
Las pruebas web verifican formatos nullable, cuota justa con push y ausencia de
probabilidades inventadas en el resumen local. Se comprueban tipos y build de
producción de Next.js; no se realiza una prueba E2E de navegador.

Se añade un workflow de pruebas para pull requests hacia main, con permisos
exclusivamente de lectura y sin pasos de despliegue. El workflow de actualización
de fuentes, Render y las configuraciones de hosting permanecen intactos.

## Pendientes fuera de Fase 1

Calibración temporal, sobre/subdispersión, validación de cobertura, encogimiento,
modelos conjuntos entre métricas, covarianzas de estimadores, precios de casas,
identificación de fixtures, evaluación económica con cuotas históricas y carga
concurrente. Los datos actuales no se actualizan ni se incorporan nuevas fuentes.
Las advertencias y límites matemáticos no sustituyen ese trabajo.

### Resultado local final

- **76 pruebas Python aprobadas**, incluidas FastAPI y 3 smoke tests de Streamlit.
- **3 pruebas de contratos web aprobadas**.
- TypeScript sin errores y build Next.js de producción completado (11 páginas).
- Comparación anterior/posterior reproducida contra el commit base.
- Un aviso de deprecación de Starlette sobre su adaptador TestClient/httpx;
  no afecta el resultado. La dependencia de producción original no se modifica.
- No existía una suite automatizada previa en el repositorio. Las dependencias
  generales permanecen sin lockfile Python: su reproducibilidad sigue pendiente.

En este entorno los tests con TestClient y el build necesitan sockets locales,
por lo que se ejecutaron fuera del aislamiento de red del comando. No se usaron
credenciales deportivas ni se escribieron datos en servicios externos durante
las pruebas. La validación local no sustituye la ejecución de CI del PR.

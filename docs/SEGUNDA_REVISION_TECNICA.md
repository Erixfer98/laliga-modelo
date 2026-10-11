# Segunda revisión técnica del PR #1

Revisión de la rama `fix/probabilidades-kelly-auditoria` a partir de `3759a12`.
Los cambios se mantienen en el PR: no se fusiona, despliega ni actualiza producción.

## Hallazgos corregidos

| Hallazgo | Consecuencia anterior | Corrección y prueba |
|---|---|---|
| Tolerancia absoluta de Brent en Kelly | Fracciones pequeñas positivas se perdían o tenían error relativo significativo | Fórmula cerrada para retornos 0/1/cuota; raíz general con precisión relativa y tolerancia absoluta mínima. Casos microscópicos y 150 distribuciones aleatorias |
| Distribuciones de retornos sin validación | Probabilidades negativas podían producir Kelly prácticamente igual a toda la banca | Masa unitaria, probabilidades y retornos finitos/no negativos; solo se normaliza error de redondeo <=1e-12 |
| `zip` truncaba reglas/cuotas | Se podía omitir silenciosamente una selección | Validación de longitudes, cuotas y matriz cuadrada normalizada |
| Cuota justa no validaba p_acierto+p_push | p=.4, push=.8 daba cuota .5 pese a ser imposible | Rechazo de masa incompatible; corrección de redondeo para evitar cuota inferior a 1 |
| Incompatibilidad por ausencia de acierto total | Over 1 y Under 2 enteros podían pagar tras un push, pero Kelly se deshabilitaba | Separación de acierto total y retorno; incompatibilidad solo si el boleto completo nunca puede devolver más de lo apostado |
| Rejilla lógica hasta 101 | Over 100 local + Over 100 visitante + victoria local se marcaba imposible | Rejilla lógica hasta 102; testigo (102,101), independiente del soporte probabilístico |
| Incompatibilidad evaluada por grupo | Un grupo que solo puede devolver la apuesta impedía combinarlo con otro partido ganador | Máximos de retorno por grupo; su producto determina si puede existir beneficio en el boleto completo |
| Límite de cola permitía 1% adicional | Contrato estricto de 1e-12 no coincidía con la validación | Umbral estricto, rechazo explícito de soportes no enteros y lambdas extremas sin OverflowError |

## Comprobación matemática

Sean X,Y conteos Poisson con medias a,b. Antes de truncar,
P(X=x,Y=y)=exp(−a−b)a^x b^y/(x!y!). El soporte dinámico excluye
P(X>K o Y>K)=sf(K,a)+sf(K,b)−sf(K,a)sf(K,b), limitado a 1e-12.
La matriz se normaliza condicionando al soporte. Las comprobaciones analíticas
consideran esa normalización; la cola limita el error absoluto de eventos.

Dixon–Coles añade (−d,+d,+d,−d) a las celdas (0,0),(0,1),(1,0),(1,1),
con d=rho*a*b*exp(−a−b). Su suma total, por filas y por columnas es cero.
Por ello conserva las marginales Poisson y cambia P(empate) en −2d.
La distribución del total Poisson(a+b) cambia en −d,+2d,−d para totales 0,1,2.
Las pruebas usan esos resultados y Skellam para el empate como oráculos
independientes, incluyendo medias cero y rho positivo/negativo admisible.

Las máscaras de Over, Under y devolución son disjuntas y exhaustivas.
Para una cuota c, p=acierto y u=push, EV=c*p+u−1 y cuota justa=(1−u)/p.
Una devolución aporta retorno bruto 1, no un acierto. En combinadas se multiplican
los retornos por resultado conjunto: una pérdida anula el boleto y un push
elimina esa pata. `prob` sigue significando todos los aciertos; puede ser cero
cuando EV y Kelly se obtienen de pagos parciales válidos.

Para retorno bruto R y fracción f, G(f)=E[log(1+f(R−1))].
G'(f)=E[(R−1)/(1+f(R−1))] y G''(f)=−E[(R−1)^2/(1+f(R−1))^2]<=0.
G'(0)=EV; si EV<=0 el óptimo es cero. En caso interior la raíz de G' es el
óptimo global por concavidad. Para retornos 0/1/c, con b=c−1 y l=1−p−u,
f=(p−l/b)/(p+l), acotado a [0,1−1e−10]. Si todo es push se devuelve cero.
La cota superior evita apostar exactamente toda la banca. Las pruebas contrastan
fórmula cerrada, derivadas, concavidad y crecimiento frente a fracciones alternativas.

La detección lógica no usa masa observada: cualquier testigo de las reglas
admitidas, cuyas líneas no superan 100, se puede representar en [0,102]^2.
Por encima de 100 se conserva igualdad con 101 y desigualdad con 101/102;
las condiciones de total, BTTS y resultado permanecen iguales. Para grupos de
partidos distintos el máximo retorno posible del boleto es el producto de los
máximos de grupo. Esto no afirma independencia empírica: esa hipótesis solo
se usa al calcular probabilidades entre partidos.

## Validación

- 76 pruebas Python: regresiones matemáticas, contratos FastAPI, smoke tests de
  Streamlit y backtest reducido. Incluyen el bloqueo explícito de Kelly y extremos
  de EV al superar 4096 escenarios de sensibilidad con pushes, conservando EV central.
- 3 pruebas web; comprobación TypeScript y build Next.js de 11 páginas.
- CI del PR ejecuta Python y web; no contiene pasos de despliegue.
- Persiste un aviso de deprecación de Starlette/TestClient que no falla las pruebas.

## Límites que permanecen

La corrección matemática no valida las lambdas estimadas ni garantiza ganancias.
Los rangos son una sensibilidad heurística sobre una rejilla; no intervalos con
cobertura probada ni extremos globales certificados. El Kelly publicado es el
mínimo de los óptimos de los escenarios evaluados, no una solución de optimización
robusta sobre un conjunto continuo. No se permite mezclar métricas del mismo partido
sin un modelo conjunto. La independencia entre partidos y el producto de cuotas
con eliminación de pushes siguen siendo hipótesis explícitas; los precios o reglas
especiales de una casa necesitan un contrato distinto. No se ejecuta backtest
predictivo completo, carga concurrente ni E2E de navegador en esta segunda revisión.

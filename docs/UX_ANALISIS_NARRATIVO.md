# Kuota — Auditoría UX y propuesta narrativa (PR independiente)

## Diagnóstico sobre main
- `web/app/partido/page.tsx`: lambdas relegadas a un acordeón inferior; antes aparecen mercados y apuesta.
- `cfg[grupo]=[centro,rango]` implica controles +/− y amplitud; la interacción expone la implementación del backend al usuario.
- La lista de mercados es exhaustiva, adecuada para análisis profundo pero no para primera interacción.
- Distribución e historial se ocultan por defecto y no enlazan visualmente con la selección.
- La selección con cuota domina un lateral sticky antes de que el usuario comprenda el análisis.
- La home exige un paso adicional; tabla y cara a cara son rutas de apoyo, no la tarea principal.

## Hipótesis UX
Narrativa visible en una sola página: enfrentamiento y métrica → lambdas y su lectura →
categoría, línea y probabilidad → distribución → evidencia y límites → decisión opcional.
No es wizard. Los enlaces a secciones permiten saltar sin perder el partido.

## Implementación de primera iteración
- Las λ local, visitante y total aparecen inmediatamente debajo del selector.
- Texto interpretativo determinista y referencia descriptiva a media de liga; no afirma causalidad.
- Las líneas de la ventana devuelta por el motor son botones de un toque, con selector Más/Menos.
- «Consultar» líneas adyacentes ajusta sólo el parámetro `cfg` que soporta el backend; no calcula odds ni probabilidades en navegador.
- Los mercados sin líneas usan opciones explícitas.
- Los controles antiguos de centro y rango se conservan como **opción avanzada temporal** para compatibilidad con los flujos existentes. No son necesarios para los cambios cotidianos.
- Distribución visible vinculada a la selección y resumen histórico sin acordeón.
- El inventario exhaustivo de mercados queda en «Ver lista completa de mercados» (cerrado por defecto); la elección habitual se hace con categoría, línea y Más/Menos. Se mantienen opciones avanzadas.
- En móvil se elimina la barra flotante de probabilidad que tapaba la lectura; la decisión aparece después de la distribución y la evidencia.
- Navegación principal simplificada a Analizar / Explorar / Boleto. Tabla, cara a cara y glosario continúan disponibles mediante «Más análisis» en escritorio y «Más» en móvil.

## Límites conocidos y decisiones pendientes de aceptación visual
- El servicio actual no ofrece calendario actual verificado; la selección del enfrentamiento sigue siendo manual.
- Las rutas y deep links originales se conservan, pero sus enlaces se reagrupan en la navegación simplificada. «Explorar» es información histórica, **no** un calendario en tiempo real.
- La lista completa se conserva en un bloque plegable para investigación avanzada; no es el recorrido inicial.
- Algunos mercados usan matrices grandes, que requieren verificar el espacio móvil real antes de aprobar el merge.
- El gráfico de barras muestra probabilidades de acierto/fallo; la liquidación/push la conserva el backend. Cualquier nueva codificación de push debe utilizar el contrato del motor.
- Una coincidencia histórica no es probabilidad futura y una λ es parámetro esperado, no marcador.
- No hay IA contextual, fixtures nuevos ni modificaciones de Poisson/DC/EV/Kelly.

## Criterios medibles
1. Lambdas en pantalla sin desplegar nada.
2. Elegir una línea ya calculada en un clic; Más/Menos en un clic.
3. Si se necesita otra línea, petición explícita `cfg` al backend, nunca probabilidad inventada.
4. Los cambios conservan partido, liga y métrica y nunca permiten añadir al boleto mientras el detalle es obsoleto.
5. Pantallas reales generadas por Playwright (390 y 1440 px) disponibles en artefactos del workflow; auditoría también a 375 y 768 px.
5. Mobile sin overflow horizontal; controles con accesibilidad de teclado y toque.
6. CI Python, TS, build, unitarias web y E2E. Capturas visuales de Playwright para revisión, no equivalentes a test de usabilidad humana.

## Fuera de alcance
PR #6 congelado, Render/R2/API-Football sin cambios, `main` sin cambios, sin merge ni despliegue.

# Fase 4 · Rediseño de Kuota

Implementación de la Etapa B sobre `main` (`5a2f1ee`), en `feature/fase-4-rediseno-ux-ui`. La revisión abarca la web Next.js. No modifica los modelos, los endpoints Python, las reglas de liquidación, el acceso privado ni los experimentos de las fases anteriores. No requiere migración de datos.

## Experiencia y sistema visual

Kuota conserva su marca y adopta una interfaz deportiva de lectura rápida: enfrentamientos manuales, identidad de equipos, mercados y probabilidades primero. La referencia FotMob/Sofascore se refleja en la navegación de fútbol, los escudos, la clasificación y las filas de mercados; no se copian sus contenidos ni se añaden agendas, horarios o estados en vivo.

- Paleta blanca/azul y noche/azul, tipografía Plus Jakarta Sans servida localmente con licencia OFL, espaciado, controles y superficies compartidos.
- iPhone: navegación inferior, menú Más con foco modal y Escape, selección de mercado accesible desde una franja fija y resumen del boleto antes de sus filas.
- Escritorio: navegación completa y columnas distintas para mercados/selección y selecciones/resumen, con panel de selección lateral. Las tablas aprovechan el ancho disponible.
- Modo claro, oscuro o sistema, persistido en `kuota-theme`. Se mantiene `kuota-v1` para contexto, boleto y banca.
- Escudos reales del catálogo existente, con iniciales si el recurso falla. No se sustituyen por escudos inventados.
- Inicio presenta el enfrentamiento elegido y tendencias descriptivas. Análisis conserva las nueve métricas, grupos, líneas, historial, condición, calificaciones y gráficos. Parámetros, historial y distribuciones se despliegan bajo demanda.
- Tabla conserva todas las columnas; móvil usa filas expandibles. Cara a cara conserva filtros y métricas. El glosario mantiene las definiciones del servidor e incorpora búsqueda diferida y estados vacíos.
- La puerta privada cambia de presentación; los manejadores de entrada, salida y cookies permanecen intactos.

## Ajustes finales antes de integrar

- Pulso muestra inicialmente cinco equipos por debajo de 1024 px. «Ver los N equipos» y «Mostrar solo cinco equipos» alternan la lista sin cambiar la métrica elegida. A partir de 1024 px se muestra siempre la lista completa: se conservan sus valores, orden, escala de barras y composición de escritorio. El botón declara su estado con `aria-expanded` y apunta a la lista mediante `aria-controls`.
- Cada mercado identifica a ambos equipos: «Cumplimiento histórico · Real Madrid: 4 de 5 partidos · Alaves: 2 de 5 partidos», usando los recuentos exactos de la API. El detalle mantiene el total y añade el desglose por equipo. No se confunden recuentos históricos con probabilidades futuras.
- Inicio y Boleto distinguen «1 selección»/«2 selecciones»; el historial distingue «1 partido»/«N partidos», y los avisos y muestras efectivas también ajustan su concordancia. Los estados vacíos y el texto de Cara a cara se refieren a datos registrados, evitando afirmar que no ocurrió un enfrentamiento solo porque no aparece en la base.
- Se agregan seis comprobaciones de navegador (tres escenarios en móvil y escritorio), incluyendo cambio de tamaño, expansión, conservación de filtros, concordancia y comparación de los recuentos mostrados con la API. Solo la comprobación de singular usa una respuesta histórica controlada; las capturas utilizan exclusivamente datos reales.

## Boleto y seguridad funcional

Las cuotas comienzan vacías. Añadir requiere una cuota finita entre 1.01 y 10000; cambiar mercado, métrica, equipos o contexto elimina la entrada pendiente. La cuota justa del modelo se identifica como tal y nunca se usa como cuota introducida. `1.90` solo aparece como entrada manual de prueba en pruebas/capturas, no como valor por defecto de la aplicación.

El boleto agrupa por liga y enfrentamiento, conserva el índice original para quitar selecciones, evita duplicados de la misma identidad y requiere confirmación para vaciar. No cambia el objeto de selección, su versión ni sus reglas. Mantiene selecciones antiguas reconocibles para que el motor explique si puede calcularlas.

La probabilidad conjunta, devoluciones, dependencias, escenarios, EV y Kelly se leen del endpoint vigente `/boleto`. No se multiplican probabilidades marginales en el cliente. Los tipos y constantes del cliente API conservan sus 26 declaraciones, comprobadas estructuralmente frente a `main`; solo se admite cancelación opcional de solicitudes. El EV individual conserva `P(acierto) × cuota + P(devolución) − 1`. La cuota justa conserva el ajuste por devolución. Los rangos y Kelly se describen como sensibilidad heurística; no se presentan como intervalos estadísticos validados ni garantía de rentabilidad.

Una combinación sin modelo disponible conserva sus selecciones y explica por qué no tiene probabilidad conjunta. Las respuestas anteriores se invalidan al cambiar contexto: solicitudes cancelables y resultados asociados a liga, parámetros, boleto, banca y revisión. No se muestra el cálculo de otro partido mientras llega el nuevo. Los errores permiten reintentar sin perder el boleto.

## Validación

- Python: `python -m pytest -q`, **135 aprobadas**. Advertencia preexistente de deprecación Starlette/httpx.
- Web: `npm test`, **8 aprobadas**; contratos nullable, devolución, resumen sin probabilidades artificiales, restauración íntegra, selección antigua, datos corruptos, identidad y agrupación.
- TypeScript: `npx tsc --noEmit --incremental false`.
- Build: `npm run build`, compilación y generación de las rutas existentes correctas.
- Playwright: **36 aprobadas**, sin omisiones (7.6 minutos reportados en la ejecución local final). Dos perfiles Chromium (390×844 táctil y 1440×1000). Autenticación, navegación, teclado, nueve métricas, grupos y líneas, contexto/solicitudes tardías, cuota vacía, comparación con respuestas reales de API, persistencia, quitar, selecciones incompatibles/antiguas, errores/reintento, glosario y temas. Incluye axe WCAG A/AA y ausencia de overflow en las seis rutas, en ambos temas, y gráficos desplegados a 320/1024 px. La revisión detectó y corrigió una etiqueta de referencia con contraste insuficiente sobre las barras.
La primera ejecución conjunta tuvo un timeout de petición mientras Python, navegador y capturas compartían recursos. Se interrumpió y se repitió la suite completa del navegador sin las otras tareas: 36 aprobadas, sin ampliar los límites de espera ni omitir casos.

- CI añade la API local y las pruebas de navegador al job web. No añade pasos de publicación.

Se verificaron adicionalmente las seis rutas a 320, 430, 768 y 1024 píxeles: 24 comprobaciones sin desbordamiento horizontal, incluyendo gráficos desplegados en Análisis. Las pruebas usan los CSV del repositorio y el servidor real; se interceptan respuestas en casos aislados para inducir retrasos, fallos de conexión y muestras históricas de tamaño uno destinadas exclusivamente a comprobar los textos. No se regeneraron resultados estadísticos porque el motor y los datos no cambian.

## Capturas reales

[Galería antes/después](fase4/capturas/README.md). Son 24 PNG comparativos de páginas realmente renderizadas con la API local: Inicio, Análisis y Boleto × móvil/escritorio × claro/oscuro × antes/después. Antes corresponde al frontend de `5a2f1ee`; después, al build de esta rama, incluidas las correcciones finales. Se añaden dos capturas móviles de Pulso expandido, una por tema. Las capturas son de página completa: las barras fijas permanecen situadas respecto al viewport inicial.

El entorno bloquea la CDN de ESPN (HTTP 403), por lo que los escudos aparecen con la alternativa real de iniciales. Los datos y probabilidades sí proceden de la API y los CSV del repositorio. Las cuotas del boleto son entradas de prueba, no precios verificados. No se usaron imágenes conceptuales.

Para repetir las capturas después: iniciar API y `npm run build && npm run start -- --port 3103`; desde `web`, ejecutar `CAPTURAS_URL=http://127.0.0.1:3103 node scripts/capturas.mjs`. Si el servidor requiere acceso, pasar su clave mediante `CAPTURAS_CLAVE`; nunca guardarla en archivos. Puede seleccionarse Chromium local mediante `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`.

## Límites de la verificación

Los perfiles móviles emulan dimensiones y tacto en Chromium: no sustituyen una comprobación en iPhone físico/Safari. axe verifica condiciones automatizables, no certifica toda la accesibilidad. Debe revisarse también la presentación con escudos accesibles fuera de este entorno. No se hizo merge, despliegue ni activación de modelos experimentales.

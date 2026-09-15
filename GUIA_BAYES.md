# Modelo bayesiano jerárquico — segunda opinión para Kuota

Tres archivos nuevos, ninguno toca `modelo.py`, `app.py` ni la BBDD.

| Archivo | Qué hace |
|---|---|
| `modelo_bayes.py` | Ajusta el modelo (PyMC) por liga × métrica y guarda las muestras en `modelos_bayes/<liga>_<metrica>.npz`. Predice leyendo ese archivo, solo con numpy |
| `diagnosticos_bayes.py` | Convergencia (r_hat, ESS, divergencias, BFMI), gráficas de traza y de fuerzas por equipo, chequeo predictivo |
| `comparacion.py` | Tabla lado a lado actual vs bayes por mercado, discrepancias ≥ umbral y EV de cada modelo contra las cuotas |
| `.github/workflows/ajustar_bayes.yml` | Reajusta las 54 combinaciones (6 ligas × 9 métricas) cada martes y sube los `.npz` al repo |

## Qué es distinto del modelo actual

- `modelo.py` calcula 4 fuerzas por equipo (ataque y defensa, en casa y fuera) como promedios ponderados divididos por el promedio de la liga. Cada fuerza sale de ~20 partidos, y con el peso por recencia, de menos.
- El bayesiano estima **un ataque y una defensa por equipo** (escala log), **una ventaja de local por liga** y un **ρ Dixon-Coles estimado** (no fijo en −0.05) en goles y goles 1T. Los equipos son *efectos aleatorios*: la liga estima cuánto pueden alejarse del promedio (`sigma_ataque`, `sigma_defensa`) y encoge hacia el promedio a los que tienen pocos datos o datos raros.
- No devuelve un número sino 1,000 escenarios plausibles. La probabilidad de un mercado es el promedio y además sale un intervalo 5%–95% (columnas `bayes_lo`, `bayes_hi`).
- Usa el mismo peso por recencia (`XI` de `modelo.py`), las mismas líneas y los mismos nombres de mercado, así que la comparación es uno a uno.

## Instalar y correr (Mac)

```
pip install pymc arviz            # solo para ajustar; la app no lo necesita
python modelo_bayes.py ajustar laliga      # 9 métricas, ~2 min con 4 núcleos
python modelo_bayes.py ajustar todas       # 6 ligas, ~10–15 min
python modelo_bayes.py "Real Madrid" "Barcelona" laliga
python comparacion.py "Real Madrid" "Barcelona" laliga cuotas_ejemplo.json 0.05
```

`ajustar` deja `diagnosticos_bayes/diagnosticos.csv` (una fila por modelo con veredicto OK / REVISAR / MAL y el motivo),
`<liga>_<metrica>_traza.png`, `<liga>_<metrica>_equipos.png` y `<liga>_<metrica>_ppc.csv`.

## Cómo leer los diagnósticos

| Columna | Bien | Revisar | Qué hacer si falla |
|---|---|---|---|
| `rhat_max` | < 1.01 | > 1.01 | subir `tune` a 2000 |
| `ess_min` | > 400 | < 400 | subir `draws` |
| `divergencias` | 0 | > 0 | `target_accept` 0.95 (en `MUESTREO`) |
| `bfmi_min` | > 0.3 | < 0.3 | igual que divergencias |
| `ppc_fuera` | 0–1 de 9 | ≥ 3 | el modelo no reproduce ese rasgo; en tiros/faltas/corners suele ser la desviación (Poisson se queda corto: negativa binomial sería el siguiente paso) |

Gráfica de traza: cada color es una cadena; deben verse como pasto mezclado, sin tendencias ni escalones.

## Enchufarlo a la app

```python
import modelo_bayes as mb, comparacion as cp
modelos = mb.cargar_modelos(liga)                       # {metrica: ModeloBayes}, lee los .npz (rápido, cachear con st.cache_resource)
r = modelos["goles"].analizar(local, visitante)         # mismo diccionario que mo.analizar + intervalos + lambda_rango
tabla = cp.comparar_partido(df, modelos, local, visitante, cuotas, umbral=0.05)
cp.discrepancias(tabla); cp.con_valor(tabla)
```

Un equipo sin partidos en la liga (recién ascendido, día 1) sale como promedio de liga con toda la incertidumbre de la liga; no rompe.

## Perillas

- `PRIOR` en `modelo_bayes.py`: lo que el modelo cree antes de ver datos. Los valores por defecto son abiertos; los datos mandan.
- `PRIOR["nu"]`: `None` = efectos Normales (por defecto). `4` = colas pesadas, encoge menos a los equipos extremos (en La Liga sube el ataque del Barça de 1.30 a 1.42 en goles 2T sin mover al resto). Cambiarlo obliga a reajustar.
- `MUESTREO`: `draws`, `tune`, `chains`, `target_accept`.
- `N_PRED` (1000): muestras guardadas por modelo. Menos = archivo más chico, probabilidades un poco más ruidosas.
- El peso por recencia viene de `modelo.py` (`XI`). Para que el bayesiano use otra memoria, recalcula `df["peso"]` antes de `ajustar(liga, metrica, df=df)`.

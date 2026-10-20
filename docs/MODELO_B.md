# Modelo B: cómo calcula Kuota la fuerza de cada equipo

Desde esta versión, `modelo.fuerzas()` usa el **Modelo B**. Reemplaza al modelo anterior, que calculaba
4 fuerzas por equipo (ataque y defensa en casa y fuera) solo con los partidos de esa sede, sin mirar a los rivales
y sin freno (`K_ENCOGE = 0`).

Explicación paso a paso con datos reales (Málaga vs Racing Santander, La Liga): `Modelo_B_paso_a_paso.xlsx`,
entregado aparte. Cada número de ese archivo es una fórmula.

## Fórmulas

Para cada equipo hay un ataque y una defensa. 1.00 = equipo promedio.

```
ataque  = (Σ peso × goles anotados + F) ÷ (Σ peso × goles esperados a favor + F)
defensa = (Σ peso × goles recibidos + F) ÷ (Σ peso × goles esperados en contra + F)

goles esperados a favor   = (prom_casa si jugó de local, prom_fuera si jugó de visita) × defensa del rival
goles esperados en contra = (prom_fuera si jugó de local, prom_casa si jugó de visita) × ataque del rival
F (freno)                 = K_ENCOGE × (prom_casa + prom_fuera) ÷ 2
peso                      = e^(−XI × días de antigüedad)

λ local     = prom_casa  × ataque del local     × defensa del visitante
λ visitante = prom_fuera × ataque del visitante × defensa del local
```

- **Freno:** son `K_ENCOGE = 10` partidos inventados, cada uno con peso 1, donde el equipo anota y recibe exactamente lo esperado.
  Con pocos partidos reales, el freno empuja las fuerzas hacia 1.00; con muchos, casi no se nota.
- **Vueltas:** cada fuerza depende de las fuerzas de los rivales, así que se calcula en vueltas. En la vuelta 1 todas las
  defensas valen 1.00 y se calculan los ataques; con esos ataques se calculan las defensas, y se repite.
  `VUELTAS = 25`; desde la vuelta 10 los valores no cambian en los primeros 5 decimales.
- **Ventaja de local:** es la misma para todos los equipos de la liga (prom_casa ÷ prom_fuera).
- **Tarjetas rojas** (`METRICAS_PROMEDIO`): todas las fuerzas valen 1.00, o sea el promedio de la liga.
  En la prueba, el modelo daba porcentajes menos exactos que el promedio en las 6 ligas.
- **Interfaz sin cambios:** `fuerzas()` devuelve `ataque` y `defensa`, y conserva `ataque_casa`, `defensa_casa`,
  `ataque_fuera` y `defensa_fuera` (con los mismos valores), así que `lambdas()`, `backtest.py`, la API, Streamlit y
  la web no cambian.
- **Rango pesimista / optimista:** λ × (1 ∓ error relativo del ataque) × (1 ∓ error relativo de la defensa).
  Es la misma fórmula t de Student de antes, ahora centrada en la λ del Modelo B. Sigue siendo sensibilidad
  heurística, no un intervalo validado.
- **Dixon-Coles** (ρ = −0.05 en goles y goles del 1er tiempo): sin cambios.

## Prueba (19/10/2026)

**Cómo se probó:** walk-forward, o sea que cada fecha se predijo solo con los partidos anteriores.
- Ligas: La Liga, Premier, Serie A, Bundesliga, Ligue 1 y Liga MX.
- Período: 23/09/2025 a 18/10/2026, con 2,014 partidos y 54,378 picks Over/Under.
- Línea de cada mercado: el promedio de la liga redondeado hacia abajo + 0.5.
- Cálculo: Poisson sin Dixon-Coles.

**Revisión independiente:** un revisor, sin ver estas conclusiones, comprobó que ningún dato del futuro se filtra a la
predicción. También reprogramó el modelo desde cero y obtuvo los mismos números (diferencia máxima 0.0002).

**Acierto del lado elegido (Over o Under)**, comparado con apostar siempre al lado más común:

| | Modelo B | Lado más común | Diferencia (rango 95 %) |
|---|---|---|---|
| Todos los picks Over/Under | 62.4 % | 58.1 % | +4.3 (+3.8 a +4.9) |
| Tiros del local | 65.6 % | 50.7 % | +14.9 (+12.2 a +17.5) |
| Faltas del local | 64.0 % | 50.7 % | +13.3 (+10.3 a +16.1) |
| Faltas total | 62.0 % | 50.8 % | +11.1 (+7.9 a +14.3) |
| Faltas del visitante | 62.0 % | 51.5 % | +10.5 (+7.7 a +13.2) |
| Tiros del visitante | 63.0 % | 53.3 % | +9.7 (+6.8 a +12.5) |
| Tiros a puerta del local | 62.3 % | 53.4 % | +8.9 (+6.5 a +11.3) |
| Tiros total | 56.0 % | 48.1 % | +7.9 (+5.1 a +10.8) |
| Tiros a puerta del visitante | 59.7 % | 52.5 % | +7.2 (+4.7 a +9.8) |
| 1X2 (contra apostar siempre "gana local") | 49.8 % | 43.5 % | +6.3 (+4.3 a +8.3) |
| Goles del local | 59.0 % | 53.4 % | +5.7 (+3.3 a +8.1) |
| Corners del local | 59.6 % | 54.3 % | +5.3 (+2.8 a +7.9) |
| Goles del visitante, 2do tiempo | 55.3 % | 50.0 % | +5.2 (+2.6 a +7.8) |
| Corners del visitante | 59.8 % | 56.5 % | +3.3 (+0.8 a +5.8) |
| Goles del local, 1er tiempo | 55.1 % | 52.1 % | +3.0 (+0.3 a +5.7) |

**Sin ventaja (el rango incluye 0):** en estos mercados la app muestra la etiqueta «sin ventaja» (`kuota.SIN_VENTAJA`).
- Goles: total del partido y del visitante.
- Goles del 1er tiempo: total y del visitante.
- Goles del 2do tiempo: total y del local.
- Corners total y tiros a puerta total.
- Amarillas y rojas: los tres mercados de cada una.

**Sin probar:** doble oportunidad, ambos anotan, mayor número, resultado por tiempo y toda la Champions League.

**Exactitud de los porcentajes** (picks donde el modelo daba entre 80 % y 90 %, sin rojas):

| | Picks | Decía (promedio) | Se cumplió |
|---|---|---|---|
| Modelo anterior | 6,677 | 84.5 % | 63.4 % |
| Modelo B | 814 | 83.0 % | 81.1 % |

El Modelo B ganó al modelo anterior y al promedio de la liga en las 6 ligas y en los 13 meses medidos.
Con cualquier freno entre 5 y 80 también le ganó al modelo anterior en las 6 ligas.

**Lo que la prueba no mide:** si se gana dinero. Para eso hay que registrar, antes de cada partido, la probabilidad del
modelo y la cuota de la casa.

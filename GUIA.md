# Guía de implementación — Modelo Poisson La Liga (end to end)

Resultado final: todos los días a las 6:00 am (Guatemala) el Excel se regenera solo con el mismo
nombre, y una web app te muestra el Poisson + Dixon-Coles de las 9 métricas para cualquier partido.

Costo: $0. Tiempo de montaje: ~45 minutos, una sola vez.

Archivos del paquete (todos van en la raíz del repositorio):

| Archivo | Qué hace |
|---|---|
| `generar_bbdd_laliga.py` | Tu notebook, como script. Descarga football-data.co.uk y escribe `datos/bbdd_laliga.xlsx` y `.csv` |
| `espn.py` | Fuente ESPN para Liga MX (scoreboard + summary de `mex.1`). Incremental: solo pide los días nuevos |
| `modelo.py` | Poisson (+ Dixon-Coles en goles) para las 9 métricas. Rango bajo–alto de cada λ (promedio ± t·desv/√n, 80%), prob. pesimista/optimista por mercado y varianza de cada equipo vs la liga |
| `app.py` | Web app (Streamlit) |
| `requirements.txt` | Librerías que necesita la app |
| `.github/workflows/actualizar.yml` | El reloj: corre el script todos los días a las 6:00 am Guatemala |
| `datos/` | Aquí viven el Excel y el CSV. Se sobrescriben en cada corrida |

---

## Paso 1 — Probar todo en tu PC (10 min)

1. Instala Python 3.12 si no lo tienes: https://www.python.org/downloads/ (marca "Add to PATH").
2. Descomprime la carpeta `laliga-modelo` en tu Drive sincronizado o donde quieras.
3. Abre una terminal dentro de la carpeta y corre:

```
pip install -r requirements.txt
python generar_bbdd_laliga.py
python modelo.py "Real Madrid" "Barcelona"
streamlit run app.py
```

Qué debes ver: el Excel y el CSV en `datos/`, las λ de las 9 métricas en la terminal, y la app
abierta en el navegador (http://localhost:8501). Si esto funciona, todo lo demás funciona.

---

## Paso 2 — Subir el proyecto a GitHub (10 min)

1. Crea una cuenta en https://github.com si no tienes.
2. Instala GitHub Desktop: https://desktop.github.com y entra con tu cuenta.
3. En GitHub Desktop: **File → Add local repository** → elige la carpeta `laliga-modelo`.
   Si dice que no es un repositorio, dale a "create a repository" ahí mismo.
4. Abajo a la izquierda escribe "Primera versión" en Summary y dale **Commit to main**.
5. Botón **Publish repository**. Puedes dejarlo privado (Streamlit Cloud lo puede leer igual).

Qué debes ver: en github.com aparece tu repositorio `laliga-modelo` con todos los archivos.

---

## Paso 3 — Activar la actualización automática (5 min)

1. En github.com, entra al repositorio → pestaña **Actions**.
2. Si pregunta, dale "I understand my workflows, go ahead and enable them".
3. Menú izquierdo: **Actualizar BBDD La Liga** → botón **Run workflow** → **Run workflow**.
4. Espera 1-2 minutos. Debe salir con un check verde.
5. Entra a `datos/` en el repositorio: el Excel debe tener un commit nuevo "BBDD actualizada dd/mm/aaaa".

Desde ahora corre solo todos los días a las 12:00 UTC (6:00 am Guatemala). Para cambiar el día u hora edita la línea `cron` en
`.github/workflows/actualizar.yml` (formato: `minuto hora * * díasemana`, en UTC; `*` = todos los días, lunes=1, viernes=5).

Nota: GitHub apaga el reloj si el repositorio pasa 60 días sin ningún commit tuyo. Si eso pasa,
vuelves a Actions y le das "Enable workflow". Con la corrida semanal normalmente no ocurre.

---

## Paso 4 — Publicar la web app (10 min)

1. Entra a https://share.streamlit.io y conéctate con tu cuenta de GitHub.
2. **Create app** → **Deploy a public app from GitHub**.
3. Repository: `tu-usuario/laliga-modelo` · Branch: `main` · Main file path: `app.py`.
4. **Deploy**. Tarda 2-3 minutos la primera vez.

Qué debes ver: una URL tipo `https://tu-usuario-laliga-modelo.streamlit.app` con la app.
Cada vez que se actualice el Excel (cada mañana), la app se redespliega sola con los datos nuevos.

Si quieres que solo tú la veas: en la app → Settings → Sharing → "Only specific people".

---

## Paso 5 — Tener el Excel en tu Drive (opcional, 2 min)

Si la carpeta `laliga-modelo` ya está dentro de tu Drive sincronizado (Paso 1), en GitHub Desktop
dale **Fetch origin → Pull** cuando quieras la versión más reciente. El archivo se llama siempre
`datos/bbdd_laliga.xlsx`, así que cualquier fórmula o Power BI que apunte ahí sigue funcionando.

---

## Cómo se usa después

- **Ver un partido**: abre la app, elige local y visitante. Arriba están las λ de las 9 métricas;
  abajo, por pestaña, los mercados con cuota justa, las fuerzas de ambos equipos y la matriz.
- **Ajustar ρ (Dixon-Coles)**: campo arriba a la derecha. Solo afecta goles y goles 1T.
- **Rangos y varianza**: `CONFIANZA` (0.90 = percentiles 10 y 90), `PJ_MIN` (5 partidos efectivos mínimos para fiarse del
  rango) y `CORTES_VAR` (0.8 / 1.2 = estable / volátil) en `modelo.py`. El Kelly del boleto usa la prob. pesimista.
- **Cambiar cuánto pesa lo reciente**: `XI` en `modelo.py`. 0.005 = un partido de hace ~140 días
  pesa la mitad. Súbelo para que pese más lo reciente.
- **Agregar una temporada**: una línea en `TEMPORADAS` de `generar_bbdd_laliga.py`.
- **Liga MX desde cero** (primera vez o si se corrompe el CSV): `python generar_bbdd.py ligamx --completo`
  (unos 3 minutos: consulta día por día desde el 1/1/2026). Después el Action solo pide los días nuevos.
- **Agregar una liga**: copia `generar_bbdd_laliga.py`, cambia `SP1` por el código de la liga
  (E0 Premier, I1 Serie A, D1 Bundesliga, F1 Ligue 1) y el diccionario `EQUIPOS`; agrega un paso
  al workflow y un selector de liga en la app.

## Si algo falla

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| Action en rojo | football-data.co.uk caído o cambió columnas | Abre el log del Action, pega el error aquí |
| App dice "KeyError: equipo" | Equipo nuevo sin nombre normalizado | Agrégalo a `EQUIPOS` y vuelve a correr |
| App no cambia tras la actualización diaria | Streamlit no detectó el commit | En share.streamlit.io → Reboot app |
| Excel se ve vacío en columnas calculadas | Estás leyendo con pandas un archivo viejo con fórmulas | Ya no pasa: el script escribe valores |
# Kuota · web

La pantalla nueva de Kuota: Next.js + Tailwind. No calcula nada; le pide todo a `api.py` (que usa `kuota.py`).

## Correrla en tu Mac (2 terminales)

1. La API, desde la carpeta del proyecto (`laliga-modelo`):
   ```
   pip install fastapi uvicorn
   uvicorn api:app --reload
   ```
   Queda en http://localhost:8000 (prueba interactiva en http://localhost:8000/docs).

2. La web, desde esta carpeta (`laliga-modelo/web`):
   ```
   npm install        # solo la primera vez
   npm run dev
   ```
   Abre http://localhost:3000.

Si la API corre en otra dirección, crea un archivo `.env.local` con `NEXT_PUBLIC_API_URL=https://tu-api...` (mira `.env.example`).

## Escudos y logos de ligas

Salen de `datos/logos.json`, que genera `logos.py` (raíz del proyecto) desde ESPN. Una vez:
```
python logos.py
```
Avisa si algún equipo queda sin escudo (se agrega su alias en `ALIAS` dentro de `logos.py`). Mientras no exista el archivo,
la web muestra las iniciales del equipo en un círculo de color.

## Dónde está cada cosa

| Carpeta / archivo | Qué es |
|---|---|
| `app/globals.css` | **La paleta y la forma de toda la app** (colores, radio de las tarjetas, tipografía Plus Jakarta Sans). Cambia aquí y cambia todo |
| `components/Nav.tsx` | Marca, selector de ligas con logo y la barra de pestañas de abajo (celular) |
| `components/Crest.tsx` | Escudo de equipo (o iniciales) y logo de liga |
| `components/Selectores.tsx` | Cabecera de partido: escudos grandes, toca un equipo para cambiarlo |
| `app/page.tsx` | Inicio |
| `app/partido/page.tsx` | Partido = Armar + Analizar en una sola pantalla |
| `app/boleto/page.tsx` | Boleto y stake (Kelly) |
| `app/cara/`, `app/tabla/`, `app/diccionario/` | Cara a cara, tabla de posiciones, diccionario |
| `components/` | Piezas: barra superior, tarjetas, pills, gráficos, tabla, detalle de la pata |
| `lib/api.ts` | Cliente de la API y los tipos de cada vista |
| `lib/store.tsx` | Memoria del navegador: liga, partido, métrica, boleto, banca (localStorage) |
| `lib/fmt.ts` | Formatos de números y fechas |

## Publicarla en internet

**1. La API (Python) en Render** — https://render.com, entrar con GitHub.
   New → Blueprint → elegir el repo `laliga-modelo` → Render lee `render.yaml` y crea el servicio `kuota-api` (plan gratis).
   Al terminar te da una URL tipo `https://kuota-api.onrender.com`. Probá `https://kuota-api.onrender.com/ligas`.
   El plan gratis se duerme tras 15 min sin uso y la primera visita tarda ~1 min en despertar; el plan de US$7/mes está siempre despierto.

**2. La web en Vercel** — https://vercel.com, entrar con GitHub.
   Add New → Project → importar `laliga-modelo` → **Root Directory: `web`** → Environment Variables:
   - `NEXT_PUBLIC_API_URL` = la URL de Render (sin barra al final)
   - `KUOTA_CLAVE` = la contraseña que compartirás con tus amigos
   Deploy. Te da una URL tipo `https://laliga-modelo.vercel.app`; en el celular, "Agregar a pantalla de inicio" y queda como app.

Cada `git push` vuelve a publicar las dos. El Action diario (6:00 am) actualiza los datos y también redespliega la API.

Pendiente para después: el analista IA y el registro de uso (hoy siguen en `app.py` de Streamlit).

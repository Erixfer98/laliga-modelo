"""
app.py — Kuota · Parlays con Datos. Las 5 grandes ligas + Liga MX.
Paginas: Inicio · Armar · Analizar · Cara a cara · Tabla · Diccionario · Admin (solo administradores).
Usuarios y registro de uso: opcionales, se configuran en Streamlit Cloud -> Settings -> Secrets (ver pagina Admin).
Sesion: al entrar se guarda un token firmado en la URL (?s=...). Si el celular manda la app a segundo plano y Streamlit
pierde la sesion, al volver se lee el token y no vuelve a pedir usuario y contraseña (dura DIAS_SESION dias).
Local: streamlit run app.py
"""

import base64
import hashlib
import hmac
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st

import modelo as mo

st.set_page_config(page_title="Kuota", page_icon="⚽", layout="centered", initial_sidebar_state="collapsed")

# ------------------------------------------------------------------ tema (sigue el tema de Streamlit: claro u oscuro)
try:
    TEMA = st.context.theme.type or "dark"
except Exception:
    TEMA = "dark"
P = {"dark": dict(app="#0b0d12", card="#141821", card2="#1b2130", txt="#eef1f6", mut="#9aa3b5", mut2="#7c8598", line="#252b3a", line2="#1f2533",
                  barbg="#262c3a", miss="#303748", mark="#ffffff", ok="#22c55e", bad="#f05252", warn="#f59e0b", acc="#3b82f6", vis="#a78bfa"),
     "light": dict(app="#f4f5f8", card="#ffffff", card2="#f1f3f6", txt="#111318", mut="#5b6373", mut2="#7a8291", line="#e1e4ea", line2="#eceef2",
                   barbg="#e3e6eb", miss="#c9cdd4", mark="#111318", ok="#15803d", bad="#c62828", warn="#b45309", acc="#2563eb", vis="#7c3aed")}[TEMA]
NUM = '"Barlow Condensed","Inter",sans-serif'   # tipografia condensada para numeros grandes (estilo marcador deportivo)

st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Barlow+Condensed:wght@600;700&display=swap');
  .stApp {{font-family:"Inter",-apple-system,"Segoe UI",Roboto,sans-serif;}}
  [data-testid="stHeader"] {{display:none;}}
  .block-container {{padding:0.3rem 0.9rem 5rem 0.9rem; max-width:640px;}}
  /* barra superior fija: marca + navegacion (+ boleto en Armar) */
  .st-key-topbar {{position:sticky; top:0; z-index:100; background:{P['app']}; margin:0 -0.9rem 4px -0.9rem; padding:6px 0.9rem 8px 0.9rem; border-bottom:1px solid {P['line']};}}
  .st-key-topbar [data-testid="stVerticalBlock"] {{gap:0.4rem;}}
  .brand {{display:flex; align-items:baseline; gap:8px; padding-top:8px; white-space:nowrap;}}
  .brand .logo {{font-family:{NUM}; font-weight:700; font-size:1.6rem; letter-spacing:.01em; color:{P['txt']}; line-height:1;}}
  .brand .slogan {{font-size:0.78rem; color:{P['mut']};}}
  .brand .user {{margin-left:auto; font-size:0.78rem; color:{P['mut']};}}
  .slip {{background:{P['card']}; border:1px solid {P['line']}; border-radius:12px; padding:8px 12px;}}
  .slip .evb {{text-align:right; flex:none; min-width:74px; margin-left:10px;}}
  /* encabezado de seccion: titulo + descripcion legible */
  .sh {{margin:14px 0 4px 0;}}
  .sh .h {{font-size:1.02rem; font-weight:700; color:{P['txt']}; letter-spacing:-.01em;}}
  .sh .d {{font-size:0.84rem; color:{P['mut']}; line-height:1.45; margin-top:2px; max-width:64ch;}}
  .card {{background:{P['card']}; border:1px solid {P['line']}; border-radius:14px; padding:14px 16px; margin:8px 0; color:{P['txt']};}}
  .card.flat {{background:{P['card2']}; border:none;}}
  .t {{font-size:0.74rem; color:{P['mut2']}; font-weight:600; letter-spacing:.01em; line-height:1.3;}}
  .row {{display:flex; justify-content:space-between; align-items:center; gap:10px;}}
  .big {{font-family:{NUM}; font-size:2.2rem; font-weight:700; line-height:1; font-variant-numeric:tabular-nums;}}
  .pct {{font-family:{NUM}; font-size:1.45rem; font-weight:700; line-height:1.05; font-variant-numeric:tabular-nums;}}
  .mid {{font-size:0.98rem; font-weight:600; line-height:1.25;}}
  .small {{font-size:0.8rem; color:{P['mut']}; line-height:1.4;}}
  .rg {{font-size:0.72rem; color:{P['mut']}; line-height:1.3; font-variant-numeric:tabular-nums;}}
  .lg-r .rg, .slip .rg, .trio .rg {{white-space:nowrap;}}
  .w {{color:{P['txt']}; font-weight:600;}}
  .note {{font-size:0.8rem; color:{P['mut']}; line-height:1.45; border-top:1px solid {P['line2']}; margin-top:10px; padding-top:8px;}}
  .dot {{display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; vertical-align:middle; position:relative; top:-1px;}}
  .bar {{height:6px; border-radius:3px; background:{P['barbg']}; position:relative; margin:8px 0 2px 0;}}
  .bar > div {{height:6px; border-radius:3px;}}
  .bar .mark {{position:absolute; top:-3px; width:2px; height:12px; background:{P['mark']}; opacity:.9;}}
  .mk {{border-top:1px solid {P['line2']}; padding:10px 0;}}
  .mk:first-child, .lg-h + .mk {{border-top:none;}}
  .tag {{display:inline-block; padding:3px 9px; border-radius:7px; font-size:0.7rem; font-weight:700; white-space:nowrap; letter-spacing:.01em;}}
  .exc {{background:#14532d; color:#bbf7d0;}} .bue {{background:#166534; color:#dcfce7;}} .reg {{background:#78350f; color:#fde68a;}}
  .mal {{background:#7f1d1d; color:#fecaca;}} .pes {{background:#450a0a; color:#fca5a5;}}
  .up {{color:{P['ok']};}} .down {{color:{P['bad']};}}
  /* libro de mercados: encabezado + una fila por mercado, columnas fijas alineadas */
  .lg-h {{display:flex; align-items:flex-end; gap:8px; padding:0 0 6px 0; border-bottom:1px solid {P['line']};}}
  .lg-r {{display:flex; align-items:center; gap:8px;}}
  .c1 {{flex:1; min-width:0;}} .cn {{width:62px; text-align:right; flex:none;}} .cq {{width:96px; text-align:right; flex:none;}}
  /* veredicto: tres numeros grandes en fila */
  .trio {{display:flex; margin:12px 0 6px 0;}} .trio > div {{flex:1; text-align:center; padding:2px 4px;}} .trio > div + div {{border-left:1px solid {P['line2']};}}
  .trio .t {{margin-top:5px;}}
  .kpi {{display:flex; gap:8px;}} .kpi > div {{flex:1; background:{P['card2']}; border-radius:10px; padding:10px 12px;}}
  .kpi.esc > div {{padding:9px 4px; text-align:center;}}
  .sec {{border-top:1px solid {P['line2']}; margin-top:12px; padding-top:10px;}} .sec > .t {{margin-bottom:6px;}}
  table.st {{width:100%; border-collapse:collapse; font-size:0.82rem; color:{P['txt']}; font-variant-numeric:tabular-nums;}}
  table.st th {{text-align:right; font-weight:500; color:{P['mut2']}; padding:6px 4px; border-bottom:1px solid {P['line']}; font-size:0.74rem;}}
  table.st th:first-child, table.st td:first-child {{text-align:left;}}
  table.st td:first-child {{color:{P['txt']};}}
  table.st td {{text-align:right; padding:7px 4px; border-bottom:1px solid {P['line2']};}}
  table.st tr:last-child td {{border-bottom:none;}}
  table.st tr.grp td {{color:{P['mut2']}; font-size:0.74rem; font-weight:600; text-align:left; padding:10px 4px 4px 4px; border-bottom:1px solid {P['line']};}}
  table.st tr.liga td {{color:{P['mut']}; font-style:italic;}}
  table.st tr.me td {{background:{P['card2']}; font-weight:600;}}
  table.mx {{border-collapse:separate; border-spacing:3px; width:100%; font-size:0.78rem; font-variant-numeric:tabular-nums;}}
  table.mx td {{text-align:center; padding:6px 0; border-radius:6px; color:{P['txt']};}}
  table.mx th {{font-size:0.72rem; color:{P['mut2']}; font-weight:500; padding:2px;}}
  .chart {{position:relative; height:110px; margin:26px 0 22px 0;}}
  .chart .bars {{display:flex; align-items:flex-end; gap:3px; height:100%;}}
  .chart .bars > div {{flex:1; border-radius:4px 4px 0 0; position:relative; min-width:6px;}}
  .chart .bars > div .v {{position:absolute; top:-16px; left:0; right:0; text-align:center; font-size:0.66rem; color:{P['txt']};}}
  .chart .bars > div .x {{position:absolute; bottom:-16px; left:0; right:0; text-align:center; font-size:0.62rem; color:{P['mut']};}}
  .chart .ln {{position:absolute; left:0; right:0; border-top:2px dashed {P['mark']}; opacity:.8;}}
  .chart .ln span {{position:absolute; right:0; top:-14px; font-size:0.66rem; color:{P['txt']};}}
  .chart .lg {{position:absolute; left:0; right:0; border-top:2px dotted #f59e0b; opacity:.9;}}
  .chart .lg span {{position:absolute; left:0; top:-14px; font-size:0.66rem; color:#d97706;}}
  .pl {{display:flex; align-items:center; gap:6px; padding:8px 0; border-bottom:1px solid {P['line2']}; font-size:0.8rem;}}
  .pl:last-child {{border-bottom:none;}}
  .pl .dt {{width:46px; flex:none; font-size:0.64rem; color:{P['mut']}; line-height:1.2;}}
  .pl .tm {{flex:1; min-width:0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; color:{P['mut']};}}
  .pl .tm.r {{text-align:right;}}
  .pl .tm.me {{font-weight:700; color:{P['txt']};}}
  .pl .sc {{width:46px; flex:none; text-align:center; font-weight:700; border-radius:6px; padding:4px 0; color:#fff; font-size:0.8rem; letter-spacing:.03em; font-variant-numeric:tabular-nums;}}
  .sc.g {{background:{P['ok']};}} .sc.p {{background:{P['bad']};}} .sc.e {{background:#6b7280;}}
  .pl .mv {{width:54px; flex:none; text-align:right; line-height:1.1;}}
  .pl .mv b {{font-size:1rem;}} .pl .mv .small {{font-size:0.62rem;}}
  .mv.ok b {{color:{P['ok']};}} .mv.no b {{color:{P['mut']};}}
  .forma {{display:inline-flex; gap:3px; vertical-align:middle;}}
  .forma span {{width:18px; height:18px; border-radius:50%; font-size:0.62rem; font-weight:700; color:#fff; display:inline-flex; align-items:center; justify-content:center;}}
  .forma .g {{background:{P['ok']};}} .forma .p {{background:{P['bad']};}} .forma .e {{background:#6b7280;}}
  .tb {{display:flex; align-items:center; gap:8px; padding:8px 0; border-bottom:1px solid {P['line2']}; font-size:0.84rem; font-variant-numeric:tabular-nums;}}
  .tb:last-child {{border-bottom:none;}}
  .tb .pos {{width:22px; text-align:center; color:{P['mut']}; font-weight:600;}}
  .tb .eq {{flex:1; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; min-width:70px;}}
  .tb .n {{width:26px; text-align:center; color:{P['mut']};}} .tb .pts {{width:30px; text-align:right; font-weight:700;}}
  .tb .z {{width:3px; height:26px; border-radius:2px;}}
  @media (max-width: 520px) {{
    .tb {{gap:5px; font-size:0.8rem;}}
    .tb .gfgc {{display:none;}}
    .tb .n {{width:20px;}} .tb .pts {{width:26px;}} .tb .pos {{width:18px;}}
    .tb .forma {{width:auto !important;}}
    .forma span {{width:14px; height:14px; font-size:0.52rem;}}
    .forma {{gap:2px;}}
  }}
  .tri {{display:flex; height:8px; border-radius:4px; overflow:hidden; background:{P['barbg']}; margin:10px 0 6px 0;}} .tri > div {{height:8px;}}
  .fm {{display:flex; align-items:center; justify-content:space-between; gap:8px; padding:5px 0; border-bottom:1px solid {P['line2']}; font-size:0.86rem;}}
  .fm:last-child {{border-bottom:none;}}
  .fm .lbl {{flex:1; text-align:center; color:{P['mut']}; font-size:0.8rem;}}
  .fm .pill {{min-width:36px; text-align:center; padding:3px 8px; border-radius:999px; font-weight:700; color:{P['txt']}; font-variant-numeric:tabular-nums;}}
  .fm .pill.on {{color:#fff;}}
  /* widgets de Streamlit: solo lo justo para que casen con las tarjetas */
  div.stButton > button {{border-radius:10px; font-weight:600;}}
  [data-testid="stExpander"] details {{border:1px solid {P['line']}; border-radius:14px; background:{P['card']};}}
  [data-testid="stExpander"] summary {{font-weight:600;}}
  [data-testid="stCaptionContainer"] p {{font-size:0.82rem; line-height:1.45; color:{P['mut']};}}
</style>""", unsafe_allow_html=True)


LIGAS = {"laliga": "La Liga", "premier": "Premier League", "seriea": "Serie A", "bundesliga": "Bundesliga", "ligue1": "Ligue 1", "ligamx": "Liga MX"}
LIGAS_DISPONIBLES = {k: v for k, v in LIGAS.items() if os.path.exists(f"datos/bbdd_{k}.csv")} or {"laliga": "La Liga"}


@st.cache_data(ttl=3600)
def datos(liga):
    return mo.cargar(f"datos/bbdd_{liga}.csv")


@st.cache_data(ttl=3600)
def incert(liga, met):
    """Incertidumbre de la lambda por equipo y condicion + variabilidad vs liga (ver modelo.incertidumbre)."""
    return mo.incertidumbre(mo.cargar(f"datos/bbdd_{liga}.csv"), met)


VAR_ICONO = {"estable": "🟢", "normal": "🟡", "volátil": "🔴", "pocos datos": "⚪"}


def chip_var(v, equipo, cond):
    """Chip de variabilidad del equipo en su condicion (casa/fuera): icono + ratio vs liga."""
    est, ratio, n = v.loc[equipo, f"estado_{cond}"], v.loc[equipo, f"ratio_{cond}"], v.loc[equipo, f"n_ef_{cond}"]
    return f'<span title="{est} · {n:.0f} partidos efectivos {cond}">{VAR_ICONO[est]} {ratio:.1f}×</span>'


def rango_txt(lo, hi, pct=True):
    return f'<span class="rg">({lo:.0%}–{hi:.0%})</span>' if pct else f'<span class="rg">({lo:.2f}–{hi:.2f})</span>'


def sec(titulo, desc=""):
    """Encabezado de seccion: titulo + una linea de descripcion legible (que es y para que sirve)."""
    st.markdown(f'<div class="sh"><div class="h">{titulo}</div>' + (f'<div class="d">{desc}</div>' if desc else "") + "</div>", unsafe_allow_html=True)


def nota(txt):
    """Nota al pie dentro de una tarjeta (como leerla)."""
    return f'<div class="note">{txt}</div>'


def eq(nombre, lado, n=None):
    """Nombre del equipo con su punto de color: local azul, visitante violeta."""
    c = P["acc"] if lado == "l" else COLOR_VIS
    return f'<span class="dot" style="background:{c}"></span>{corto(nombre, n) if n else nombre}'


ss = st.session_state
ss.setdefault("liga", next(iter(LIGAS_DISPONIBLES)))
if ss.liga not in LIGAS_DISPONIBLES:
    ss.liga = next(iter(LIGAS_DISPONIBLES))
df = datos(ss.liga)
lista = mo.equipos(df)
ss.setdefault("parlay", [])
ss.setdefault("pagina", "Inicio")
ss.setdefault("gen", 0)   # cambia para reiniciar los widgets al saltar de pagina
ss.setdefault("banca", 1000.0)
ss.setdefault("chat", [])       # historial del asistente IA
ss.setdefault("ctx_ia", "")     # contexto de la vista actual que se le pasa a la IA
GOL = ("goles", "goles_1t", "goles_2t")
MAYOR_NUMERO = ("tiros", "tiros_a_puerta", "corners", "faltas", "amarillas")   # metricas con mercado "quien hace mas"
NOM = mo.NOMBRES
NOM_CORTO = {"goles": "Goles", "goles_1t": "Goles 1T", "goles_2t": "Goles 2T", "tiros": "Tiros", "tiros_a_puerta": "Tiros a puerta",
             "corners": "Corners", "faltas": "Faltas", "amarillas": "Amarillas", "rojas": "Rojas"}
COLOR_VIS = P["vis"]   # color del visitante en graficos y cara a cara (el local usa P["acc"])
HORA_GT = ZoneInfo("America/Guatemala")
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


# ================================================================== asistente IA flotante (todas las vistas)
PREFERIDOS_IA = ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "moonshotai/kimi-k2-instruct", "qwen/qwen3-32b",
                 "meta-llama/llama-4-maverick-17b-128e-instruct", "llama-3.1-8b-instant"]


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def modelo_disponible(url_chat, key):
    """Pregunta al proveedor que modelos hay y elige el mejor de la lista de preferidos. Evita errores de modelo retirado."""
    try:
        r = requests.get(url_chat.replace("/chat/completions", "/models"), headers={"Authorization": f"Bearer {key}"}, timeout=10)
        ids = [m["id"] for m in r.json().get("data", [])]
        for p in PREFERIDOS_IA:
            if p in ids:
                return p
        libres = [i for i in ids if not any(x in i for x in ("whisper", "guard", "tts", "embed"))]
        return libres[0] if libres else PREFERIDOS_IA[0]
    except Exception:
        return PREFERIDOS_IA[0]


def ia_cfg():
    try:
        key = st.secrets["IA_KEY"]
    except Exception:
        return None
    url = st.secrets.get("IA_URL", "https://api.groq.com/openai/v1/chat/completions")
    modelo = st.secrets.get("IA_MODELO") or modelo_disponible(url, key)
    return {"key": key, "url": url, "modelo": modelo}


SISTEMA_IA = ("Eres el analista de Kuota, una app de apuestas para las 5 grandes ligas europeas y la Liga MX con un modelo Poisson/Dixon-Coles "
              "(de él salen la probabilidad, la cuota justa, el EV, la calificación y el stake) más estadísticas descriptivas. "
              "Responde en español, directo y breve (máximo ~150 palabras salvo que pidan más). Fundamenta o debate con los datos del contexto: "
              "probabilidad del modelo, cuota justa, cumplimiento histórico, medias vs liga, resultados recientes. No inventes cifras que no estén en el contexto; "
              "si te falta un dato dilo. Señala riesgos: patas del mismo partido no son independientes, muestras chicas (N<5), equipos recién ascendidos con pocos datos, "
              "y que el modelo no sabe de lesiones, alineaciones ni árbitro. Si el usuario da una cuota, calcula EV = prob × cuota − 1 y di si hay valor. "
              "Termina siempre con una recomendación concreta: apostar, no apostar o qué revisar.")


def preguntar_ia(pregunta):
    c = ia_cfg()
    if c is None:
        return "Falta configurar IA_KEY en Secrets (ver página Admin)."
    msgs = [{"role": "system", "content": SISTEMA_IA + "\n\nContexto de la vista actual:\n" + (ss.ctx_ia or "sin contexto")}]
    msgs += [{"role": m["rol"], "content": m["txt"]} for m in ss.chat[-8:]]
    msgs.append({"role": "user", "content": pregunta})
    payload = {"model": c["modelo"], "messages": msgs, "temperature": 0.4, "max_tokens": int(st.secrets.get("IA_MAX_TOKENS", 3000))}
    if "gpt-oss" in c["modelo"]:
        payload["reasoning_effort"] = "low"   # los modelos razonadores gastan tokens pensando; asi dejan tokens para responder
    try:
        r = requests.post(c["url"], headers={"Authorization": f"Bearer {c['key']}", "Content-Type": "application/json"},
                          json=payload, timeout=90)
        if r.status_code != 200:
            return f"Error {r.status_code}: {r.text[:200]}"
        msg = r.json()["choices"][0]["message"]
        texto = (msg.get("content") or "").strip()
        if not texto:   # respuesta vacia (se agoto el limite razonando): usar el razonamiento o avisar
            texto = (msg.get("reasoning") or msg.get("reasoning_content") or "").strip()
        return texto or "El modelo no devolvió texto. Pregunta de nuevo o cambia IA_MODELO en Secrets (ej. llama-3.3-70b-versatile)."
    except Exception as ex:
        return f"Error: {ex}"




# ================================================================== usuarios y registro de uso (opcional, via Secrets)
def cfg_usuarios():
    try:
        return dict(st.secrets["usuarios"])
    except Exception:
        return {}


def cfg_admins():
    try:
        return [x.strip() for x in str(st.secrets.get("admins", "")).split(",") if x.strip()]
    except Exception:
        return []


def gh():
    """Config de GitHub para guardar el registro de uso en la rama `uso` (no redespliega la app)."""
    try:
        tok = st.secrets["GH_TOKEN"]
    except Exception:
        return None
    repo = st.secrets.get("GH_REPO", "Erixfer98/laliga-modelo")
    return {"h": {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"},
            "repo": repo, "rama": st.secrets.get("GH_RAMA_USO", "uso"), "archivo": "uso.csv"}


def gh_leer_uso(g):
    r = requests.get(f"https://api.github.com/repos/{g['repo']}/contents/{g['archivo']}?ref={g['rama']}", headers=g["h"], timeout=10)
    if r.status_code != 200:
        return None, "fecha,usuario,accion,detalle\n"
    return r.json()["sha"], base64.b64decode(r.json()["content"]).decode()


def gh_asegurar_rama(g):
    r = requests.get(f"https://api.github.com/repos/{g['repo']}/git/ref/heads/{g['rama']}", headers=g["h"], timeout=10)
    if r.status_code == 200:
        return
    main = requests.get(f"https://api.github.com/repos/{g['repo']}/git/ref/heads/main", headers=g["h"], timeout=10).json()
    requests.post(f"https://api.github.com/repos/{g['repo']}/git/refs", headers=g["h"], timeout=10,
                  json={"ref": f"refs/heads/{g['rama']}", "sha": main["object"]["sha"]})


def registrar_uso(accion, detalle=""):
    """Agrega una linea a uso.csv en la rama `uso`. Devuelve un texto de diagnostico; silencioso para el usuario."""
    g = gh()
    if g is None:
        return "sin GH_TOKEN"
    try:
        gh_asegurar_rama(g)
        for _ in range(2):   # un reintento por si otro usuario escribio al mismo tiempo
            sha, contenido = gh_leer_uso(g)
            linea = f"{datetime.now(HORA_GT):%Y-%m-%d %H:%M:%S},{ss.get('usuario', 'invitado')},{accion},{str(detalle).replace(',', ';')}\n"
            body = {"message": f"uso: {ss.get('usuario', 'invitado')} {accion}", "branch": g["rama"],
                    "content": base64.b64encode((contenido + linea).encode()).decode()}
            if sha:
                body["sha"] = sha
            r = requests.put(f"https://api.github.com/repos/{g['repo']}/contents/{g['archivo']}", headers=g["h"], json=body, timeout=10)
            if r.status_code in (200, 201):
                ss.uso_diag = f"OK {r.status_code}"
                return ss.uso_diag
            ss.uso_diag = f"PUT {r.status_code}: {r.text[:200]}"
    except Exception as ex:
        ss.uso_diag = f"error: {ex}"
    return ss.uso_diag


usuarios = cfg_usuarios()
DIAS_SESION = 30   # cuanto dura la sesion guardada en la URL sin volver a pedir contraseña


def secreto_sesion():
    """Clave con la que se firma el token de sesion. Usa SESION_SECRETO de Secrets si existe; si no, una derivada de las
    contraseñas (sirve igual; solo cambia -y cierra las sesiones- si cambias alguna contraseña)."""
    try:
        s = st.secrets.get("SESION_SECRETO", "")
    except Exception:
        s = ""
    return str(s) or hashlib.sha256("|".join(f"{k}:{v}" for k, v in sorted(usuarios.items())).encode()).hexdigest()


def firma(usuario, exp):
    return hmac.new(secreto_sesion().encode(), f"{usuario}|{exp}".encode(), hashlib.sha256).hexdigest()[:24]


def token_sesion(usuario):
    """usuario|vencimiento|firma, en base64 para que viaje limpio en la URL."""
    exp = int(time.time()) + DIAS_SESION * 86400
    return base64.urlsafe_b64encode(f"{usuario}|{exp}|{firma(usuario, exp)}".encode()).decode().rstrip("=")


def usuario_de_token(tok):
    """Usuario del token si la firma es valida, no vencio y el usuario sigue existiendo; None si no."""
    try:
        usuario, exp, f = base64.urlsafe_b64decode((tok + "=" * (-len(tok) % 4)).encode()).decode().split("|")
        if hmac.compare_digest(f, firma(usuario, exp)) and int(exp) > time.time() and usuario in usuarios:
            return usuario
    except Exception:
        pass
    return None


if usuarios and "usuario" not in ss:
    u_tok = usuario_de_token(st.query_params.get("s", ""))
    if u_tok:
        ss.usuario = u_tok          # la sesion se reconstruye desde la URL: no pide login
    else:
        st.markdown('### Kuota <span class="small" style="font-weight:400">· Parlays con Datos</span>', unsafe_allow_html=True)
        st.markdown('<div class="card"><div class="t">Acceso</div><div class="small">Ingresa con tu usuario y contraseña.</div></div>', unsafe_allow_html=True)
        u = st.text_input("Usuario")
        c = st.text_input("Contraseña", type="password")
        if st.button("Entrar", width="stretch"):
            if u in usuarios and str(usuarios[u]) == c:
                ss.usuario = u
                st.query_params["s"] = token_sesion(u)   # la URL guarda la sesion: al volver del segundo plano no pide login
                registrar_uso("login")
                st.rerun()
            st.error("Usuario o contraseña incorrectos")
        st.stop()
if not usuarios:
    ss.setdefault("usuario", "invitado")
ES_ADMIN = ss.usuario in cfg_admins() or not usuarios


# ================================================================== datos por equipo
def historial(equipo, met, n, condicion=None):
    h = mo.ultimos_n(df, equipo, met, 80)
    if condicion:
        h = h[h.condicion == condicion]
    h = h.head(n).copy()
    h["gano"] = (h.a_favor > h.en_contra).astype(int)
    h["empato"] = (h.a_favor == h.en_contra).astype(int)
    h["perdio"] = (h.a_favor < h.en_contra).astype(int)
    h["no_perdio"] = 1 - h.perdio
    h["no_gano"] = 1 - h.gano
    h["btts"] = ((h.a_favor > 0) & (h.en_contra > 0)).astype(int)
    return h


def cumple(h, mk, lado):
    col = mk["col_l"] if lado == "l" else mk["col_v"]
    return (h[col] > mk["linea"]) if mk["over"] else (h[col] < mk["linea"])


def calificar(p, tasa):
    s = 0.6 * p + 0.4 * tasa
    for lim, txt, cls in ((0.78, "Excelente", "exc"), (0.68, "Buena", "bue"), (0.56, "Regular", "reg"), (0.45, "Mala", "mal")):
        if s >= lim:
            return txt, cls
    return "Pésima", "pes"


def kelly(p, cuota):
    """Fraccion de banca segun Kelly: (b*p - q) / b, con b = cuota - 1. Negativa = sin valor."""
    b = cuota - 1
    return (b * p - (1 - p)) / b if b > 0 else 0.0


NIVELES = [("Excelente", "exc"), ("Buena", "bue"), ("Regular", "reg"), ("Mala", "mal"), ("Pésima", "pes")]


def bajar_nivel(cls):
    return NIVELES[min([c for _, c in NIVELES].index(cls) + 1, len(NIVELES) - 1)]


def evaluar(mk, hl, hv, vol=None):
    """vol = {equipo: True si es volátil en su condicion}. La pata baja un nivel si algún equipo que participa en la pata
    es volátil (Total/Resultado/Mayor número = los dos; grupo de un equipo = ese)."""
    cl, cv = cumple(hl, mk, "l"), cumple(hv, mk, "v")
    n = len(hl) + len(hv)
    tasa = (cl.sum() + cv.sum()) / n if n else 0
    txt, cls = calificar(mk["prob"], tasa)
    # varianza: si un equipo de la pata es volátil frente a la liga, baja un nivel
    equipos_pata = list(vol) if (vol and mk["grupo"] in ("Resultado", "Total", "Mayor número")) else [mk["grupo"]]
    volatil = bool(vol) and any(vol.get(t, False) for t in equipos_pata)
    if volatil:
        txt, cls = bajar_nivel(cls)
    return {"hl": int(cl.sum()), "nl": len(hl), "hv": int(cv.sum()), "nv": len(hv), "tasa": tasa, "cal": txt, "cls": cls,
            "serie_l": cl, "serie_v": cv, "volatil": volatil, "tag": ("↕ " if volatil else "") + txt}


# ================================================================== mercados (linea configurable)
def lineas(centro, rango):
    return [x for x in np.arange(centro - rango, centro + rango + 0.01, 1.0) if x > 0]


def mercados(r, met, local, visitante, cfg):
    """cfg = {grupo: (centro, rango)}. Devuelve lista de mercados con su regla de evaluacion historica. Cada mercado
    trae prob (lambda central) y lo / hi = pesimista / optimista: la misma probabilidad calculada en las esquinas
    bajo/alto de las lambdas (minimo y maximo de las 4 esquinas; en mercados de un solo equipo, de sus 2 extremos).
    Todo sale de las mismas lambdas bajo-alto que se muestran arriba."""
    m, lam_l, lam_v = r["matriz"], r["lambda_local"], r["lambda_visitante"]
    esq, (ll, lh), (vl, vh) = r["rango"]["esquinas"], r["rango"]["lam_l"], r["rango"]["lam_v"]
    k = m.shape[0]; tot = np.add.outer(np.arange(k), np.arange(k))
    out = []

    def add(nombre, grupo, f, col_l, col_v, linea, over, region):
        """f(matriz) -> probabilidad; se evalua en la matriz central y en las 4 esquinas."""
        p, ps = f(m), [f(e) for e in esq.values()]
        out.append({"mercado": nombre, "grupo": grupo, "prob": float(min(max(p, 0), 1)),
                    "lo": float(min(max(min(ps), 0), 1)), "hi": float(min(max(max(ps), 0), 1)),
                    "col_l": col_l, "col_v": col_v, "linea": linea, "over": over, "region": region})

    def add1(nombre, grupo, lam, lam_lo, lam_hi, ln, over, col_l, col_v, region):
        """mercado de un solo equipo: Poisson con su lambda central, baja y alta."""
        ps = [mo.prob_over(x, ln) for x in (lam, lam_lo, lam_hi)]
        if not over: ps = [1 - x for x in ps]
        out.append({"mercado": nombre, "grupo": grupo, "prob": float(ps[0]), "lo": float(min(ps[1:])), "hi": float(max(ps[1:])),
                    "col_l": col_l, "col_v": col_v, "linea": ln, "over": over, "region": region})

    p1 = lambda x: np.tril(x, -1).sum(); px = lambda x: np.trace(x); p2 = lambda x: np.triu(x, 1).sum(); bt = lambda x: x[1:, 1:].sum()
    # quien gana / quien hace mas: sale de la matriz
    if met in GOL:
        add(f"Gana {local}", "Resultado", p1, "gano", "perdio", 0.5, True, lambda x, y: x > y)
        add("Empate", "Resultado", px, "empato", "empato", 0.5, True, lambda x, y: x == y)
        add(f"Gana {visitante}", "Resultado", p2, "perdio", "gano", 0.5, True, lambda x, y: x < y)
        add(f"{local} o empate", "Resultado", lambda x: p1(x) + px(x), "no_perdio", "no_gano", 0.5, True, lambda x, y: x >= y)
        add(f"{visitante} o empate", "Resultado", lambda x: p2(x) + px(x), "no_gano", "no_perdio", 0.5, True, lambda x, y: x <= y)
        add("Ambos anotan: Sí", "Resultado", bt, "btts", "btts", 0.5, True, lambda x, y: x > 0 and y > 0)
        add("Ambos anotan: No", "Resultado", lambda x: 1 - bt(x), "btts", "btts", 0.5, False, lambda x, y: x == 0 or y == 0)
    for ln in lineas(*cfg["Total"]):
        add(f"Total Over {ln}", "Total", lambda x, ln=ln: x[tot > ln].sum(), "total", "total", ln, True, lambda x, y, ln=ln: x + y > ln)
        add(f"Total Under {ln}", "Total", lambda x, ln=ln: 1 - x[tot > ln].sum(), "total", "total", ln, False, lambda x, y, ln=ln: x + y < ln)
    if met in MAYOR_NUMERO:
        que = NOM[met].lower()
        add(f"Más {que}: {local}", "Mayor número", p1, "gano", "perdio", 0.5, True, lambda x, y: x > y)
        add(f"Más {que}: empate", "Mayor número", px, "empato", "empato", 0.5, True, lambda x, y: x == y)
        add(f"Más {que}: {visitante}", "Mayor número", p2, "perdio", "gano", 0.5, True, lambda x, y: x < y)
    for ln in lineas(*cfg[local]):
        add1(f"{local} Over {ln}", local, lam_l, ll, lh, ln, True, "a_favor", "en_contra", lambda x, y, ln=ln: x > ln)
        add1(f"{local} Under {ln}", local, lam_l, ll, lh, ln, False, "a_favor", "en_contra", lambda x, y, ln=ln: x < ln)
    for ln in lineas(*cfg[visitante]):
        add1(f"{visitante} Over {ln}", visitante, lam_v, vl, vh, ln, True, "en_contra", "a_favor", lambda x, y, ln=ln: y > ln)
        add1(f"{visitante} Under {ln}", visitante, lam_v, vl, vh, ln, False, "en_contra", "a_favor", lambda x, y, ln=ln: y < ln)
    return out


def centro_defecto(lam, met):
    if met == "goles": return 2.5
    if met in GOL: return 1.5
    if met == "rojas": return 0.5
    return max(round(lam) - 0.5, 0.5)


# ================================================================== piezas visuales
def barra(valor, marca, maximo, color="#2b6cb0"):
    pct = min(valor / maximo, 1) * 100 if maximo else 0
    mk = min(marca / maximo, 1) * 100 if maximo else 0
    return f'<div class="bar"><div style="width:{pct:.0f}%;background:{color}"></div><div class="mark" style="left:{mk:.0f}%"></div></div>'


def delta(v, ref, dec=1):
    return f'<span class="{"up" if v - ref >= 0 else "down"}">{v - ref:+.{dec}f}</span>'


def corto(nombre, n=12):
    return nombre if len(nombre) <= n else nombre[:n - 1] + "…"


def tabla_modelos(local, visitante, lam_l, lam_v, rango_l, rango_v, ml, var):
    """Esperado por el modelo en una tabla con columnas alineadas: λ · rango 80% · liga · Δ · var. Una fila por equipo y el total."""
    (ll, lh), (vl, vh) = rango_l, rango_v
    h = '<table class="st"><tr><th>Equipo</th><th>λ</th><th>rango</th><th>liga</th><th>Δ</th><th>var.</th></tr>'
    h += '<tr class="grp"><td colspan="6">Poisson · rango de confianza 80%</td></tr>'
    for nm, lam, lo, hi, ref, chip in ((eq(local, "l", 13), lam_l, ll, lh, ml["local"], chip_var(var, local, "casa")),
                                       (eq(visitante, "v", 13), lam_v, vl, vh, ml["visitante"], chip_var(var, visitante, "fuera")),
                                       ("Total", lam_l + lam_v, ll + vl, lh + vh, ml["total"], "")):
        h += f'<tr><td>{nm}</td><td class="w">{lam:.2f}</td><td>{lo:.2f}–{hi:.2f}</td><td>{ref:.2f}</td><td>{delta(lam, ref, 2)}</td><td>{chip}</td></tr>'
    return h + "</table>" + nota("λ = cantidad esperada · liga = media de la liga en esa condición · Δ = λ menos la media · "
                                "var. = qué tan variable es el equipo frente a la liga (🟢 estable 🟡 normal 🔴 volátil ⚪ pocos datos)")


def escenarios_html(mk):
    """Cuadricula pesimista · Poisson · optimista: probabilidad y cuota justa de cada escenario."""
    tiles = [(nm, mk[k], f"justa {mo.cuota_justa(mk[k]):.2f}") for nm, k in (("Pesimista", "lo"), ("Poisson", "prob"), ("Optimista", "hi"))]
    return '<div class="kpi esc">' + "".join(f'<div><div class="t">{nm}</div><div class="pct">{p:.0%}</div><div class="rg">{s}</div></div>'
                                             for nm, p, s in tiles) + "</div>"


def medias_html():
    """Medias de la liga por metrica (todas las temporadas cargadas) y % de partidos por encima de la linea tipica del total."""
    h = '<table class="st"><tr><th></th><th>Local</th><th>Visit.</th><th>Total</th><th>Línea</th><th>Over</th></tr>'
    for met, (col_l, col_v, _) in mo.METRICAS.items():
        d = df.dropna(subset=[col_l, col_v]); tot = d[col_l] + d[col_v]
        ln = float(np.floor(tot.mean()) + 0.5)          # la linea .5 mas cercana a la media del total
        dec = 2 if met in GOL or met == "rojas" else 1
        h += (f'<tr><td>{NOM_CORTO[met]}</td><td>{d[col_l].mean():.{dec}f}</td><td>{d[col_v].mean():.{dec}f}</td><td class="w">{tot.mean():.{dec}f}</td>'
              f'<td>{ln}</td><td class="w">{(tot > ln).mean():.0%}</td></tr>')
    return h + "</table>"


def stats_partido_html(g, a, b):
    """Ficha de un partido estilo FotMob: valor del local · metrica · valor del visitante. La pastilla de color = el que hizo mas."""
    home, away = g.equipo_local_txt, g.equipo_visitante_txt
    c_home, c_away = (P["acc"], COLOR_VIS) if home == a else (COLOR_VIS, P["acc"])
    h = (f'<div class="row" style="margin-bottom:4px"><div class="mid" style="color:{c_home}">{corto(home)}</div>'
         f'<div class="small">{g.temporada_txt} · {g.fecha:%d/%m/%Y}</div><div class="mid" style="color:{c_away}">{corto(away)}</div></div>')
    for met, (col_l, col_v, _) in mo.METRICAS.items():
        vl, vv = g[col_l], g[col_v]
        if pd.isna(vl) or pd.isna(vv):
            continue
        vl, vv = int(vl), int(vv)
        pl = f'<span class="pill on" style="background:{c_home}">{vl}</span>' if vl > vv else f'<span class="pill">{vl}</span>'
        pv = f'<span class="pill on" style="background:{c_away}">{vv}</span>' if vv > vl else f'<span class="pill">{vv}</span>'
        h += f'<div class="fm">{pl}<div class="lbl">{NOM_CORTO[met]}</div>{pv}</div>'
    return h


def chart_barras(h, col, linea, media_liga, over, color):
    """Barras partido a partido (antiguo -> reciente). Linea blanca punteada = linea del mercado; naranja = media liga."""
    vals = h[col].iloc[::-1].tolist()
    if not vals:
        return '<div class="small">sin partidos con ese filtro</div>'
    mx = max(max(vals), linea, media_liga, 1) * 1.15
    bars = ""
    for v, (_, g) in zip(vals, h.iloc[::-1].iterrows()):
        ok = (v > linea) if over else (v < linea)
        c = color if ok else P["miss"]
        bars += (f'<div style="height:{max(v / mx * 100, 2):.0f}%;background:{c}" title="{g.rival} {g.fecha}">'
                 f'<span class="v">{v:.0f}</span><span class="x">{"C" if g.condicion == "Casa" else "F"}</span></div>')
    return (f'<div class="chart"><div class="bars">{bars}</div>'
            f'<div class="ln" style="bottom:{linea / mx * 100:.0f}%"><span>línea {linea:.1f}</span></div>'
            f'<div class="lg" style="bottom:{media_liga / mx * 100:.0f}%"><span>liga {media_liga:.1f}</span></div></div>')


def tabla_stats(h, linea, over, ref_f, ref_c, ref_t):
    """Media, mediana, desviacion, min, max y % cumple para a favor / en contra / total, con fila de referencia liga."""
    if h.empty:
        return '<div class="small">sin partidos con ese filtro</div>'
    def col(c):
        s = h[c]; pct = ((s > linea) if over else (s < linea)).mean()
        return [s.mean(), s.median(), s.std(ddof=0), s.min(), s.max(), pct]
    A, C, T = col("a_favor"), col("en_contra"), col("total")
    filas = ["Media", "Mediana", "Desv. est.", "Mín", "Máx", f"% {'Over' if over else 'Under'} {linea}"]
    html = '<table class="st"><tr><th></th><th>A favor</th><th>En contra</th><th>Total</th></tr>'
    for i, nm in enumerate(filas):
        f = (lambda v: f"{v:.0%}") if i == 5 else (lambda v: f"{v:.1f}")
        html += f"<tr><td>{nm}</td><td>{f(A[i])}</td><td>{f(C[i])}</td><td>{f(T[i])}</td></tr>"
    html += f'<tr class="liga"><td>Media liga</td><td>{ref_f:.1f}</td><td>{ref_c:.1f}</td><td>{ref_t:.1f}</td></tr></table>'
    return html


def lista_partidos(equipo, h, mk, lado):
    """Partido a partido estilo FotMob: local - marcador (verde gano / rojo perdio / gris empate) - visitante,
    racha G/E/P y el valor de la pata en cada partido (verde = cumplio)."""
    if h.empty:
        return f'<div class="card"><div class="mid">{equipo}</div><div class="small">sin partidos con ese filtro</div></div>'
    col = mk["col_l"] if lado == "l" else mk["col_v"]
    serie = cumple(h, mk, lado)
    filas, forma = "", []
    for (_, g), ok in zip(h.iterrows(), serie):
        gl, gv = (int(x) for x in g.marcador.split("-"))
        casa = g.condicion == "Casa"
        gf, gc = (gl, gv) if casa else (gv, gl)
        res = "g" if gf > gc else ("p" if gf < gc else "e")
        forma.append(res)
        home, away = (equipo, g.rival) if casa else (g.rival, equipo)
        if col in ("a_favor", "en_contra", "total"):
            det = f"{int(g.a_favor)}·{int(g.en_contra)}" if col == "total" else ("a favor" if col == "a_favor" else "en contra")
            if met == "goles" and col != "total":
                det = ""
            val = f'<b>{int(g[col])}</b><div class="small">{det}</div>'
        else:
            val = f'<b>{"✓" if ok else "✗"}</b>'
        filas += (f'<div class="pl"><div class="dt">{g.fecha}<br>{"Casa" if casa else "Fuera"}</div>'
                  f'<div class="tm r{" me" if casa else ""}">{home}</div><div class="sc {res}">{gl}-{gv}</div>'
                  f'<div class="tm{"" if casa else " me"}">{away}</div><div class="mv {"ok" if ok else "no"}">{val}</div></div>')
    G, E, Pp = forma.count("g"), forma.count("e"), forma.count("p")
    dots = "".join(f'<span class="{x}">{x.upper()}</span>' for x in forma[::-1])
    que = {"a_favor": "a favor", "en_contra": "en contra", "total": "total"}.get(col, "cumple")
    return (f'<div class="card"><div class="row"><div class="mid">{eq(equipo, lado)}</div>'
            f'<div class="small">{G}G {E}E {Pp}P</div></div>'
            f'<div class="row" style="margin:4px 0 6px 0"><div class="forma">{dots}</div>'
            f'<div class="small">{NOM[met].lower()} {que} · <span class="w">{int(serie.sum())}/{len(h)}</span> cumplió</div></div>'
            f'{filas}' + nota("Racha: antiguo → reciente. Marcador verde = ganó, rojo = perdió, gris = empate. Valor en verde = en ese partido se cumplió la pata.") + '</div>')


def matriz_html(m, local, visitante, region, k=6):
    mx = m[:k, :k].max()
    h = '<table class="mx"><tr><th></th>' + "".join(f"<th>{y}</th>" for y in range(k)) + "</tr>"
    for x in range(k):
        h += f"<tr><th>{x}</th>"
        for y in range(k):
            p = m[x, y]; a = 0.15 + 0.85 * (p / mx)
            col = f"rgba(46,158,91,{a:.2f})" if region(x, y) else (f"rgba(90,98,112,{a * 0.7:.2f})" if TEMA == "dark" else f"rgba(156,163,175,{a * 0.8:.2f})")
            h += f'<td style="background:{col}">{p * 100:.0f}</td>'
        h += "</tr>"
    return h + "</table>" + nota(f"Filas = {local} · columnas = {visitante}. Cada celda es el % de ese marcador exacto según Poisson. Verde = marcadores con los que gana la pata; más intenso = más probable.")


def distribucion_html(m, mk, etiqueta):
    k = m.shape[0]
    if mk["grupo"] == "Total":
        tot = np.add.outer(np.arange(k), np.arange(k))
        dist = np.array([m[tot == s].sum() for s in range(k * 2 - 1)])
    else:
        dist = m.sum(axis=1 if mk["col_l"] == "a_favor" else 0)
    cond = (lambda s: s > mk["linea"]) if mk["over"] else (lambda s: s < mk["linea"])
    hi = len(dist)
    while hi > 1 and dist[hi - 1] < 0.005: hi -= 1
    hi = min(len(dist), max(hi, int(mk["linea"]) + 2))
    mx = dist[:hi].max()
    bars = "".join(f'<div style="height:{max(dist[s] / mx * 100, 2):.0f}%;background:{"#2e9e5b" if cond(s) else P["miss"]}">'
                   f'<span class="v">{dist[s]:.0%}</span><span class="x">{s}</span></div>' for s in range(hi))
    return f'<div class="chart"><div class="bars">{bars}</div></div>' + nota(f"Probabilidad de cada cantidad de {etiqueta} según Poisson. Verde = cantidades con las que gana la pata.")



def diferencia_html(m, mk, local, visitante, etiqueta):
    """Barras de P(local - visitante = d) segun la matriz Poisson. Verde = diferencias con las que gana la pata."""
    k = m.shape[0]
    dif = np.subtract.outer(np.arange(k), np.arange(k))
    ds = list(range(-(k - 1), k))
    dist = np.array([m[dif == d].sum() for d in ds])
    lo, hi = 0, len(ds)
    while lo < len(ds) - 1 and dist[lo] < 0.005: lo += 1
    while hi > lo + 1 and dist[hi - 1] < 0.005: hi -= 1
    mx = dist[lo:hi].max()
    bars = "".join(f'<div style="height:{max(dist[i] / mx * 100, 2):.0f}%;background:{"#2e9e5b" if mk["region"](max(ds[i], 0), max(-ds[i], 0)) else P["miss"]}">'
                   f'<span class="v">{dist[i]:.0%}</span><span class="x">{ds[i]:+d}</span></div>' for i in range(lo, hi))
    return (f'<div class="chart"><div class="bars">{bars}</div></div>'
            + nota(f"Diferencia de {etiqueta}: {local} menos {visitante}, según Poisson. Positivo = más el local, negativo = más el visitante. Verde = gana la pata."))


# ================================================================== tabla de posiciones y tendencias
def temporada_actual():
    return df.sort_values("fecha")["temporada_txt"].iloc[-1]


def tabla_posiciones(temp):
    d = df[df.temporada_txt == temp]
    filas = {}
    for _, g in d.sort_values("fecha").iterrows():
        gl, gv = int(g.goles_local_val), int(g.goles_visitante_val)
        for eq, gf, gc in ((g.equipo_local_txt, gl, gv), (g.equipo_visitante_txt, gv, gl)):
            f = filas.setdefault(eq, {"equipo": eq, "J": 0, "G": 0, "E": 0, "P": 0, "GF": 0, "GC": 0, "PTS": 0, "forma": []})
            f["J"] += 1; f["GF"] += gf; f["GC"] += gc
            res = "g" if gf > gc else ("p" if gf < gc else "e")
            f["G" if res == "g" else ("P" if res == "p" else "E")] += 1
            f["PTS"] += 3 if res == "g" else (1 if res == "e" else 0)
            f["forma"].append(res)
    t = pd.DataFrame(filas.values())
    if t.empty:
        return t
    t["DG"] = t.GF - t.GC
    return t.sort_values(["PTS", "DG", "GF"], ascending=False).reset_index(drop=True)


def html_tabla(t, resaltar=(), compacta=False):
    n = len(t)
    h = ('<div class="card"><div class="tb" style="border:none;padding:2px 0"><div class="z"></div><div class="pos"></div><div class="eq t">Equipo</div>'
         '<div class="n t">J</div><div class="n t">G</div><div class="n t">E</div><div class="n t">P</div>'
         + ('' if compacta else '<div class="n t gfgc" style="width:44px">GF-GC</div>') + '<div class="n t">DG</div><div class="pts t">PTS</div>'
         + ('' if compacta else '<div class="forma" style="width:102px"></div>') + '</div>')
    for i, f in t.iterrows():
        pos = i + 1
        z = P["ok"] if pos <= 4 else ("#f59e0b" if pos <= 6 else (P["bad"] if pos > n - 3 else "transparent"))
        forma = "".join(f'<span class="{x}">{x.upper()}</span>' for x in f.forma[-5:])
        h += (f'<div class="tb"{" style=background:" + P["card2"] if f.equipo in resaltar else ""}><div class="z" style="background:{z}"></div>'
              f'<div class="pos">{pos}</div><div class="eq">{f.equipo}</div><div class="n">{f.J}</div><div class="n">{f.G}</div>'
              f'<div class="n">{f.E}</div><div class="n">{f.P}</div>' + ('' if compacta else f'<div class="n gfgc" style="width:44px">{f.GF}-{f.GC}</div>')
              + f'<div class="n">{f.DG:+d}</div><div class="pts">{f.PTS}</div>' + ('' if compacta else f'<div class="forma" style="width:102px">{forma}</div>') + '</div>')
    return h + nota("Franja verde = Champions · ámbar = Europa · roja = descenso (orientativo). Forma: antiguo → reciente.") + "</div>"


def tendencias(met, n=5):
    """Equipos con mayor y menor promedio total de la metrica en sus ultimos n partidos, vs media liga."""
    ml = mo.medias_liga(df, met)
    filas = []
    for eq in lista:
        h = mo.ultimos_n(df, eq, met, n)
        if len(h) >= 3:
            filas.append({"equipo": eq, "prom": h.total.mean(), "favor": h.a_favor.mean(), "contra": h.en_contra.mean()})
    t = pd.DataFrame(filas).sort_values("prom", ascending=False)
    return t, ml["total"]


# ================================================================== boleto (se usa en la barra superior y en Inicio)
def resumen_boleto():
    """Devuelve (prob, cuota, ev, prob_pesimista, prob_optimista) del boleto o None.
    Pesimista / optimista = producto de la prob. pesimista / optimista de cada pata."""
    legs = ss.parlay
    if not legs:
        return None
    prob = float(np.prod([l["prob"] for l in legs])); cuota = float(np.prod([l["cuota"] for l in legs]))
    lo = float(np.prod([l.get("lo", l["prob"]) for l in legs])); hi = float(np.prod([l.get("hi", l["prob"]) for l in legs]))
    return prob, cuota, prob * cuota - 1, lo, hi


def slip_html(detalle=False):
    """Resumen del boleto en una fila: patas y cuota a la izquierda, probabilidad y EV a la derecha.
    detalle=True agrega la linea pesimista / optimista."""
    rb = resumen_boleto()
    if not rb:
        return ""
    prob, cuota, ev, plo, phi = rb
    h = (f'<div class="slip"><div class="row"><div class="c1"><div class="t">Boleto · {len(ss.parlay)} pata{"s" if len(ss.parlay) > 1 else ""}</div>'
         f'<div class="mid">cuota {cuota:.2f}</div><div class="rg">justa {mo.cuota_justa(prob)}</div></div>'
         f'<div class="evb"><div class="t">EV · {prob:.0%}</div><div class="pct {"up" if ev > 0 else "down"}">{ev:+.2f}</div></div></div>')
    if detalle:
        h += f'<div class="small" style="margin-top:6px">pesimista {plo:.0%} (EV {plo * cuota - 1:+.2f}) · optimista {phi:.0%} (EV {phi * cuota - 1:+.2f})</div>'
    return h + "</div>"


# ================================================================== navegacion (barra superior fija)
paginas = ["Inicio", "Armar", "Analizar", "Cara a cara", "Tabla", "Diccionario"] + (["Admin"] if ES_ADMIN else [])
with st.container(key="topbar"):
    top1, top2 = st.columns([3, 1])
    top1.markdown('<div class="brand"><span class="logo">Kuota</span><span class="slogan">Parlays con datos</span></div>', unsafe_allow_html=True)
    if usuarios:
        if top2.button(f"Salir · {ss.usuario}", width="stretch"):
            registrar_uso("logout")
            st.query_params.clear()      # borra el token de la URL: la proxima vez si pide login
            for k in list(ss.keys()):
                del ss[k]
            st.rerun()
    else:
        top2.markdown(f'<div class="brand"><span class="user">{ss.usuario}</span></div>', unsafe_allow_html=True)
    pagina = st.segmented_control("Página", paginas, default=ss.pagina if ss.pagina in paginas else "Inicio",
                                  label_visibility="collapsed", key=f"pag_w{ss.gen}") or ss.pagina
    ss.pagina = pagina
    if pagina == "Armar" and ss.parlay:      # el boleto viaja fijo con la barra mientras armas
        st.markdown(slip_html(), unsafe_allow_html=True)
if pagina not in ("Diccionario", "Admin"):
    liga_sel = st.pills("Liga", list(LIGAS_DISPONIBLES), format_func=lambda k: LIGAS_DISPONIBLES[k], default=ss.liga,
                        label_visibility="collapsed", key=f"liga_w{ss.gen}") or ss.liga
    if liga_sel != ss.liga:
        ss.liga = liga_sel; ss.gen += 1; st.rerun()
LIGA = LIGAS_DISPONIBLES[ss.liga]


def ir_a(pag):
    ss.pagina = pag; ss.gen += 1; st.rerun()


def selector_partido():
    """Local y visitante. El partido elegido se recuerda al cambiar de pagina (y por liga)."""
    c1, c2 = st.columns(2)
    rec = ss.setdefault("partido_liga", {}).get(ss.liga, {})
    ini_l = rec.get("local") if rec.get("local") in lista else ("Real Madrid" if "Real Madrid" in lista else lista[0])
    local = c1.selectbox("Local", lista, index=lista.index(ini_l))
    otros = [e for e in lista if e != local]
    ini_v = rec.get("visitante") if rec.get("visitante") in otros else otros[0]
    visitante = c2.selectbox("Visitante", otros, index=otros.index(ini_v))
    ss.partido_liga[ss.liga] = {"local": local, "visitante": visitante}
    return local, visitante


def torneos_recientes():
    """Torneo vigente y el anterior (los dos ultimos por fecha), en orden cronologico."""
    return df.groupby("temporada_txt")["fecha"].max().sort_values().index.tolist()[-2:]


# ================================================================== PAGINA INICIO
if pagina == "Inicio":
    temp = temporada_actual()
    ult = df["fecha"].max()
    n_temp = len(df[df.temporada_txt == temp])
    val_txt = ""
    if os.path.exists("datos/validacion.json"):
        import json
        _v = json.load(open("datos/validacion.json")).get("ligas", {}).get(ss.liga)
        if _v:
            val_txt = (f'<span class="{"up" if _v.get("ok") and not _v.get("avisos") else "down"}">datos {"validados ✓" if _v.get("ok") else "con errores"}</span>'
                       f' · {_v.get("vacias", 0)} celdas vacías · ')
    st.markdown(f'<div class="card"><div class="row"><div class="mid">{LIGA}</div><div class="small">temporada {temp}</div></div>'
                f'<div class="trio"><div><div class="big">{n_temp}</div><div class="t">partidos jugados</div></div>'
                f'<div><div class="big">{ult:%d} {MESES[ult.month - 1]}</div><div class="t">último dato</div></div>'
                f'<div><div class="big">{len(lista)}</div><div class="t">equipos</div></div></div>'
                + nota(f'{val_txt}{len(df)} partidos cargados en total ({" y ".join(torneos_recientes())}). Se actualiza todos los días a las 6:00 am.') + '</div>',
                unsafe_allow_html=True)
    if ss.parlay:
        sec("Boleto en curso", "Lo que llevas armado. Sigue en Armar para agregar patas o revisar el stake.")
        st.markdown(slip_html(detalle=True), unsafe_allow_html=True)
    a, b = st.columns(2)
    if a.button("Armar parlay", width="stretch"):
        ir_a("Armar")
    if b.button("Analizar una pata", width="stretch"):
        ir_a("Analizar")

    sec("Medias de liga por partido", "Promedio de todos los partidos cargados. Línea = la .5 más cercana a la media del total; "
        "Over = en qué porcentaje de partidos el total superó esa línea. Sirve para saber qué tan normal es un Over antes de mirar a los equipos.")
    st.markdown(f'<div class="card">{medias_html()}</div>', unsafe_allow_html=True)

    t = tabla_posiciones(temp)
    sec("Tabla · top 6", f"Calculada con los partidos cargados de la temporada {temp}. La tabla completa está en la página Tabla.")
    st.markdown(html_tabla(t.head(6), compacta=True), unsafe_allow_html=True)
    ss.ctx_titulo = f"Inicio · {LIGA} · tabla {temp}"
    medias_ia = "; ".join(f"{NOM[m]} local {mo.medias_liga(df, m)['local']:.2f} visita {mo.medias_liga(df, m)['visitante']:.2f} total {mo.medias_liga(df, m)['total']:.2f}"
                          for m in mo.METRICAS)
    ss.ctx_ia = (f"Vista: Inicio. Liga {LIGA}. Temporada {temp}, datos al {ult:%d/%m/%Y}. Medias de liga por partido: {medias_ia}. Tabla: " +
                 "; ".join(f"{i + 1}. {f.equipo} {f.PTS} pts (J{f.J} G{f.G} E{f.E} P{f.P}, DG {f.DG:+d})" for i, f in t.iterrows()) +
                 ("\nBoleto actual: " + "; ".join(f"{l['mercado']} ({l['partido']}, modelo {l['prob']:.0%}, cuota {l['cuota']})" for l in ss.parlay) if ss.parlay else "\nBoleto vacío."))

    sec("Tendencias · últimos 5 partidos", "Promedio del equipo (a favor + en contra) en sus últimos 5 partidos, comparado con la media de la liga. "
        "Sirve para elegir qué partido y mercado analizar.")
    met_h = st.pills("Métrica tendencias", list(mo.METRICAS), format_func=lambda x: NOM[x], default="corners", label_visibility="collapsed")
    if met_h:
        tt, media = tendencias(met_h)
        def fila(f):
            return (f'<div class="mk"><div class="row"><div class="mid">{f.equipo}</div><div class="pct">{f.prom:.1f} '
                    f'<span class="rg">{f.prom - media:+.1f} vs liga</span></div></div>'
                    f'{barra(f.prom, media, max(tt.prom.max(), media) * 1.1, P["ok"] if f.prom >= media else P["mut"])}'
                    f'<div class="rg">a favor {f.favor:.1f} · en contra {f.contra:.1f}</div></div>')
        st.markdown(f'<div class="card"><div class="row" style="margin-bottom:4px"><div class="t">{NOM[met_h]} por partido · todos los equipos</div><div class="t">media liga {media:.1f}</div></div>'
                    + "".join(fila(f) for _, f in tt.iterrows()) + nota("Ordenados de mayor a menor. Barra = promedio del equipo; marca vertical = media de la liga.") + '</div>', unsafe_allow_html=True)

# ================================================================== PAGINA DICCIONARIO
elif pagina == "Diccionario":
    DIC = [
        ("Modelo", "λ (lambda)", "Cantidad esperada de la métrica para un equipo en este partido, según el modelo. Ej. λ corners 5.2 = se esperan unos 5 corners de ese equipo."),
        ("Modelo", "Poisson", "Fórmula que convierte una λ en probabilidades: cuántas veces sale 0, 1, 2, 3… Se usa para goles, tiros, corners, faltas y tarjetas."),
        ("Modelo", "Dixon-Coles (ρ)", "Corrección a Poisson solo para goles: ajusta los marcadores 0-0, 1-0, 0-1 y 1-1, que Poisson estima mal. ρ negativo = más empates bajos."),
        ("Modelo", "Ataque / defensa", "Fuerza del equipo relativa a la liga. 1.00 = promedio; 1.30 = produce 30% más que un equipo promedio; 0.80 = 20% menos."),
        ("Modelo", "Peso por recencia", "Los partidos recientes pesan más que los viejos al calcular las fuerzas. Un partido de hace ~140 días pesa la mitad que uno de hoy."),
        ("Modelo", "Matriz de resultados", "Tabla con la probabilidad de cada marcador exacto (filas = local, columnas = visitante). Verde = marcadores con los que gana la pata."),
        ("Modelo", "Rango bajo–alto de λ", "Entre paréntesis junto a cada λ: hasta dónde puede estar equivocado el promedio del equipo. Se calcula sobre sus propios partidos (con la misma recencia del modelo): promedio ± t × desviación estándar ÷ √n. El multiplicador t sale de la distribución t de Student y baja solo conforme hay más partidos (3 partidos 1.89, 21 partidos 1.33, muchos 1.28); el rango cubre el 80% de los casos. Mide confianza en la λ, no cuánto varía un partido: eso ya lo cubre Poisson."),
        ("Modelo", "Pesimista / optimista", "La probabilidad del mercado calculada con el mismo Poisson pero con las λ del extremo que va en contra (pesimista) o a favor (optimista) de la pata. Salen de las mismas λ bajo–alto que ves arriba, así que un Over y su Under siempre cuadran. El EV pesimista usa la prob. pesimista: si sigue positivo, la pata aguanta aunque el promedio esté algo inflado."),
        ("Modelo", "Varianza vs liga (🟢🟡🔴⚪)", "Ancho del rango del equipo (relativo a su promedio, en esa condición: casa o fuera) dividido entre el ancho mediano de los equipos de la liga. 🟢 estable < 0.8×, 🟡 normal 0.8–1.2×, 🔴 volátil > 1.2×, ⚪ pocos datos = menos de 5 partidos efectivos en esa condición; ahí se usa la dispersión típica de la liga en lugar de la del equipo."),
        ("Modelo", "Encogimiento (K)", "Al calcular la fuerza de un equipo se le suman 10 partidos 'extra' al promedio de la liga. Así un equipo con pocos partidos o una racha rara no se va a extremos (λ = 0 o λ = 8). El backtest mostró que sin esto el modelo decía 85% y acertaba 79%; con esto dice 85% y acierta 85%."),
        ("Mercados", "Cuota justa", "1 dividido entre la probabilidad Poisson. Es la cuota a la que no ganas ni pierdes a largo plazo. Si la casa paga más que la justa, hay valor."),
        ("Mercados", "EV (valor esperado)", "prob. × cuota − 1. Positivo = a largo plazo ganas; negativo = pierdes. EV +0.10 = ganas 10 centavos por cada Q1 apostado, en promedio."),
        ("Mercados", "Over / Under", "Más de / menos de una línea. Total Over 2.5 goles = 3 o más goles en el partido. Las líneas .5 no permiten empate."),
        ("Mercados", "Línea y ± líneas", "Línea = el centro que quieres ver (ej. 9.5 corners). ± líneas = cuántas líneas alrededor mostrar (±2 con 9.5 muestra 7.5, 8.5, 9.5, 10.5 y 11.5)."),
        ("Mercados", "1X2 / doble oportunidad", "1 = gana local, X = empate, 2 = gana visitante. 1X = local o empate; X2 = visitante o empate."),
        ("Mercados", "Ambos anotan (BTTS)", "Sí = los dos equipos marcan al menos un gol. No = al menos uno se queda en cero."),
        ("Mercados", "Total / Local / Visitante", "Grupos de mercados. Total suma los dos equipos; Local y Visitante son la métrica de un solo equipo."),
        ("Mercados", "Mayor número", "Qué equipo termina con más tiros, tiros a puerta, corners, faltas o amarillas (o empate). Probabilidad = matriz Poisson de la métrica."),
        ("Validación", "Últ. N", "Contra cuántos partidos recientes de cada equipo se valida la pata. N chico = forma actual; N grande = tendencia estable."),
        ("Validación", "X/N cumplió", "En cuántos de los últimos N partidos del equipo se habría cumplido ese mercado. 4/5 = pasó en 4 de 5."),
        ("Validación", "Calificación", "60% probabilidad Poisson + 40% cumplimiento histórico. Excelente ≥ 78%, Buena ≥ 68%, Regular ≥ 56%, Mala ≥ 45%, Pésima el resto."),
        ("Validación", "↕ Equipo volátil", "Un equipo de la pata es 🔴 volátil frente a la liga (el local en casa o el visitante fuera; en Total, Resultado y Mayor número cuentan los dos): la calificación baja un nivel."),
        ("Validación", "Como jugarán", "Filtro: solo partidos del local jugando en casa y del visitante jugando fuera."),
        ("Validación", "Media / mediana / desv. est.", "Media = promedio. Mediana = valor del medio (resiste goleadas raras). Desviación estándar = qué tanto varía de partido a partido; alta = equipo irregular."),
        ("Validación", "Media liga", "Promedio de todos los partidos cargados. Referencia para saber si un equipo está por encima o por debajo de lo normal."),
        ("Validación", "Línea típica y % Over (Inicio)", "Línea .5 más cercana a la media de la liga de esa métrica (ej. 2.5 goles, 9.5 corners). % Over = en qué porcentaje de los partidos cargados el total superó esa línea. Sirve para saber qué tan normal es un Over antes de mirar a los equipos."),
        ("Validación", "Cara a cara", "Enfrentamientos directos entre los dos equipos solo en el torneo vigente y el anterior. Récord y la ficha completa de cada partido (las 9 métricas): la pastilla de color marca al equipo que hizo más. Son pocos partidos (2 o 3): contexto, no prueba."),
        ("Validación", "Tabla de λ", "Una fila por equipo y el total: λ = esperado del modelo, bajo–alto = hasta dónde puede estar equivocado ese promedio, liga = media de la liga en esa condición, Δ = λ menos la media liga, var. = varianza del equipo vs liga (🟢🟡🔴⚪ y ×N)."),
        ("Banca", "Banca", "Dinero total destinado a apostar. Todo el stake se calcula como porcentaje de esto."),
        ("Banca", "Kelly", "Fracción de banca que maximiza el crecimiento si la probabilidad fuera exacta: ((cuota−1)·p − (1−p)) / (cuota−1). Se calcula con la prob. pesimista del boleto (producto de las pesimistas de cada pata): si con esa aún hay valor, el stake aguanta un modelo demasiado optimista."),
        ("Banca", "½, ¼, ⅛ Kelly", "La mitad, un cuarto y un octavo del Kelly completo. Para parlays usa ¼ o ⅛: menos crecimiento pero mucha menos probabilidad de quebrar."),
        ("Banca", "Patas no independientes", "Dos patas del mismo partido (ej. gana Madrid + over 2.5) están relacionadas; multiplicar sus probabilidades da un número inexacto."),
        ("Datos", "Fuente", "football-data.co.uk para las 5 ligas europeas; ESPN para Liga MX. Se descarga todos los días a las 6:00 am (Guatemala) por GitHub Actions."),
        ("Datos", "Columnas _val", "goles, goles 1er/2do tiempo, tiros, tiros a puerta, corners, faltas, amarillas y rojas, cada una para local y visitante."),
        ("Datos", "Jornada", "Estimada: partido n-ésimo de cada equipo en la temporada. Un aplazado se cuenta cuando se jugó."),
        ("Datos", "Temporada", "Europa: formato 2025-26 (agosto a mayo). Liga MX: Clausura AAAA (enero-junio) y Apertura AAAA (julio-diciembre), Liguilla incluida."),
    ]
    sec("Diccionario", "Qué significa cada término que ves en la app, en palabras simples. Escribe para filtrar.")
    q = st.text_input("Buscar", placeholder="Buscar un término…", label_visibility="collapsed").strip().lower()
    grupos_d = list(dict.fromkeys(g for g, _, _ in DIC))
    DESC_G = {"Modelo": "Cómo se calculan las probabilidades.", "Mercados": "Qué es cada apuesta y cómo leer cuota y EV.",
              "Validación": "Cómo se comprueba una pata contra el historial y qué significa la calificación.",
              "Banca": "Cuánto apostar.", "Datos": "De dónde salen los datos y cómo se ordenan."}
    for g in grupos_d:
        items = [(t_, d_) for gg, t_, d_ in DIC if gg == g and (not q or q in t_.lower() or q in d_.lower())]
        if not items:
            continue
        sec(g, DESC_G.get(g, ""))
        st.markdown('<div class="card">' +
                    "".join(f'<div class="mk"><div class="mid">{t_}</div><div style="margin-top:3px;font-size:0.86rem;line-height:1.5;color:{P["txt"]}">{d_}</div></div>' for t_, d_ in items)
                    + '</div>', unsafe_allow_html=True)

# ================================================================== PAGINA TABLA
elif pagina == "Tabla":
    temps = sorted(df.temporada_txt.unique(), reverse=True)
    temp = st.selectbox("Temporada", temps, label_visibility="collapsed")
    t = tabla_posiciones(temp)
    sec(f"Posiciones · {temp}", f"{LIGA}. Calculada con los partidos cargados en la base. Las zonas de Champions, Europa y descenso son orientativas (4 / 2 / 3).")
    st.markdown(html_tabla(t), unsafe_allow_html=True)

# ================================================================== PAGINA ADMIN
elif pagina == "Admin":
    sec("Calidad de datos", "Resultado de la última revisión automática de cada base: vacíos, duplicados, descanso > final, tiros a puerta > tiros y negativos.")
    if os.path.exists("datos/validacion.json"):
        import json
        val = json.load(open("datos/validacion.json"))
        filas_v = ""
        for k, r in val["ligas"].items():
            estado = ("ERROR", P["bad"]) if not r.get("ok") else (("AVISO", "#f59e0b") if r.get("avisos") else ("OK", P["ok"]))
            det = "<br>".join(r.get("errores", []) + r.get("avisos", []))
            filas_v += (f'<div class="mk"><div class="row"><div class="mid">{LIGAS.get(k, k)}</div><span class="tag" style="background:{estado[1]};color:#fff">{estado[0]}</span></div>'
                        f'<div class="small">{r.get("partidos", 0)} partidos · {r.get("equipos", "?")} equipos · último {r.get("ultimo", "?")} · '
                        f'{r.get("vacias", 0)} celdas vacías · {r.get("duplicados", 0)} duplicados</div>'
                        + (f'<div class="small down">{det}</div>' if det else "") + '</div>')
        st.markdown(f'<div class="card"><div class="t" style="margin-bottom:4px">Última validación · {val["fecha"]}</div>{filas_v}</div>', unsafe_allow_html=True)
    else:
        st.info("Todavía no hay reporte de validación (se genera en la próxima corrida del Action).")
    sec("Usuarios y uso", "Quién puede entrar y cuánto usa la app. Se configura en Streamlit Cloud → Settings → Secrets.")
    if not usuarios:
        st.markdown('<div class="card"><div class="mid">Acceso abierto (sin usuarios configurados)</div>'
                    '<div class="small" style="margin-top:6px">Para activar usuarios y el registro de uso, en Streamlit Cloud → tu app → Settings → Secrets pega:</div></div>',
                    unsafe_allow_html=True)
        st.code('admins = "erick"\nGH_TOKEN = "github_pat_xxx"      # token con permiso Contents: read/write sobre el repo\nGH_REPO = "Erixfer98/laliga-modelo"\n\n[usuarios]\nerick = "tu-contraseña"\namigo1 = "otra-contraseña"', language="toml")
        st.caption("El uso se guarda en uso.csv dentro de la rama `uso` del repo (no toca `main`, así la app no se redespliega). "
                   "Token: GitHub → Settings → Developer settings → Fine-grained tokens → solo este repo, permiso Contents read/write.")
    else:
        c_ia = ia_cfg()
        st.markdown(f'<div class="card"><div class="t">Analista IA</div><div class="mid">{"Configurado · modelo " + c_ia["modelo"] if c_ia else "Sin configurar"}</div>'
                    '<div class="small" style="margin-top:6px">Secrets: IA_KEY (clave), y opcionales IA_URL (endpoint compatible OpenAI) e IA_MODELO. '
                    'Gratis: Groq (console.groq.com, URL https://api.groq.com/openai/v1/chat/completions) o Gemini (aistudio.google.com, URL https://generativelanguage.googleapis.com/v1beta/openai/chat/completions).</div></div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="card"><div class="t">Usuarios activos</div><div class="mid">' + " · ".join(usuarios) + '</div>'
                    '<div class="small" style="margin-top:6px">Se agregan o quitan en Streamlit Cloud → Settings → Secrets, bloque [usuarios]. El cambio aplica al instante.</div></div>',
                    unsafe_allow_html=True)
        g = gh()
        if g is None:
            st.warning("Sin GH_TOKEN en Secrets: los usuarios funcionan pero no se registra el uso.")
        else:
            with st.expander("Diagnóstico del registro de uso"):
                st.write(f"Repo: `{g['repo']}` · rama: `{g['rama']}` · último intento: `{ss.get('uso_diag', 'ninguno en esta sesión')}`")
                if st.button("Probar registro ahora"):
                    st.write("Resultado:", registrar_uso("prueba"))
                    rr = requests.get(f"https://api.github.com/repos/{g['repo']}", headers=g["h"], timeout=10)
                    st.write("Acceso al repo:", rr.status_code, "" if rr.status_code == 200 else rr.text[:200])
                    rb = requests.get(f"https://api.github.com/repos/{g['repo']}/branches/{g['rama']}", headers=g["h"], timeout=10)
                    st.write(f"Rama `{g['rama']}`:", rb.status_code, "existe" if rb.status_code == 200 else "no existe / sin permiso")
            _, contenido = gh_leer_uso(g)
            from io import StringIO
            uso = pd.read_csv(StringIO(contenido))
            if uso.empty:
                st.info("Todavía no hay registros de uso.")
            else:
                uso["fecha"] = pd.to_datetime(uso["fecha"])
                hace7 = datetime.now(HORA_GT).replace(tzinfo=None) - pd.Timedelta(days=7)
                res = uso.groupby("usuario").agg(eventos=("accion", "size"), logins=("accion", lambda s: (s == "login").sum()),
                                                 boletos=("accion", lambda s: (s == "pata").sum()),
                                                 ultimo=("fecha", "max")).sort_values("eventos", ascending=False)
                res["últ. 7 días"] = uso[uso.fecha >= hace7].groupby("usuario").size().reindex(res.index).fillna(0).astype(int)
                res["ultimo"] = res["ultimo"].dt.strftime("%d/%m %H:%M")
                st.markdown(f'<div class="kpi"><div><div class="t">Eventos</div><div class="big">{len(uso)}</div></div>'
                            f'<div><div class="t">Usuarios</div><div class="big">{uso.usuario.nunique()}</div></div>'
                            f'<div><div class="t">Últ. 7 días</div><div class="big">{int((uso.fecha >= hace7).sum())}</div></div></div>',
                            unsafe_allow_html=True)
                st.dataframe(res.rename(columns={"eventos": "eventos", "ultimo": "último uso"}), width="stretch")
                with st.expander("Últimos 50 eventos"):
                    st.dataframe(uso.sort_values("fecha", ascending=False).head(50), hide_index=True, width="stretch")

# ================================================================== PAGINA CARA A CARA (torneo vigente + anterior)
elif pagina == "Cara a cara":
    local, visitante = selector_partido()
    temps = torneos_recientes()
    par = df[df.temporada_txt.isin(temps) & (((df.equipo_local_txt == local) & (df.equipo_visitante_txt == visitante)) |
                                             ((df.equipo_local_txt == visitante) & (df.equipo_visitante_txt == local)))].sort_values("fecha", ascending=False)
    solo_casa = st.toggle(f"Solo con {local} en casa", value=False)
    if solo_casa:
        par = par[par.equipo_local_txt == local]
    es_a = par.equipo_local_txt == local                                   # True donde el local elegido jugo en casa
    ga = np.where(es_a, par.goles_local_val, par.goles_visitante_val)
    gb = np.where(es_a, par.goles_visitante_val, par.goles_local_val)
    G, E, Pp = int((ga > gb).sum()), int((ga == gb).sum()), int((ga < gb).sum())
    n = len(par)
    txt_temps = " y ".join(temps)
    iv = lambda x: "?" if pd.isna(x) else int(x)

    # 1) record estilo FotMob: victorias · empates · victorias + barra tricolor
    sec("Récord directo", f"Solo {txt_temps}" + (f", con {local} en casa" if solo_casa else "") + ". Son pocos partidos: sirven como contexto, no como prueba.")
    if n == 0:
        st.markdown(f'<div class="card"><div class="mid">Sin enfrentamientos</div><div class="small">{local} y {visitante} no se han cruzado en {txt_temps}'
                    + (" con el local en casa" if solo_casa else "") + '.</div></div>', unsafe_allow_html=True)
    else:
        tri = "".join(f'<div style="width:{x / n * 100:.0f}%;background:{c}"></div>' for x, c in ((G, P["acc"]), (E, "#6b7280"), (Pp, COLOR_VIS)))
        st.markdown(f'<div class="card"><div class="trio" style="margin-top:0">'
                    f'<div><div class="big" style="color:{P["acc"]}">{G}</div><div class="t">{eq(local, "l", 14)}</div></div>'
                    f'<div><div class="big" style="color:#6b7280">{E}</div><div class="t">empate{"s" if E != 1 else ""}</div></div>'
                    f'<div><div class="big" style="color:{COLOR_VIS}">{Pp}</div><div class="t">{eq(visitante, "v", 14)}</div></div></div>'
                    f'<div class="tri">{tri}</div><div class="small">{n} partido{"s" if n != 1 else ""} · victorias de cada uno y empates</div></div>', unsafe_allow_html=True)

        # 2) partido a partido: la ficha completa de cada enfrentamiento, ya abierta (estilo FotMob)
        sec("Partido a partido", f"La ficha completa de cada enfrentamiento (las 9 métricas). 🟢 ganó {local} · 🔴 ganó {visitante} · ⚪ empate. "
            "La pastilla de color marca al equipo que hizo más en esa métrica.")
        for _, g in par.iterrows():
            gl, gv = int(g.goles_local_val), int(g.goles_visitante_val)
            a_, b_ = (gl, gv) if g.equipo_local_txt == local else (gv, gl)
            punto = "🟢" if a_ > b_ else ("🔴" if a_ < b_ else "⚪")
            with st.expander(f"{punto} {g.fecha:%d/%m/%y} · {g.equipo_local_txt} {gl}-{gv} {g.equipo_visitante_txt} · {g.temporada_txt}", expanded=True):
                st.markdown(stats_partido_html(g, local, visitante), unsafe_allow_html=True)

    ss.ctx_titulo = f"Cara a cara · {local} vs {visitante}"
    ss.ctx_ia = (f"Vista: Cara a cara. Liga {LIGA}. {local} vs {visitante}, solo {txt_temps}" + (f", solo con {local} en casa" if solo_casa else "") +
                 f". Récord: {local} {G} victorias, {E} empates, {visitante} {Pp} victorias en {n} partidos. "
                 + (("Partidos (reciente→antiguo): " +
                     "; ".join(f"{g.fecha:%d/%m/%y} {g.equipo_local_txt} {iv(g.goles_local_val)}-{iv(g.goles_visitante_val)} {g.equipo_visitante_txt} "
                               f"(tiros {iv(g.tiros_local_val)}-{iv(g.tiros_visitante_val)}, corners {iv(g.corners_local_val)}-{iv(g.corners_visitante_val)}, "
                               f"faltas {iv(g.faltas_local_val)}-{iv(g.faltas_visitante_val)}, amarillas {iv(g.amarillas_local_val)}-{iv(g.amarillas_visitante_val)})"
                               for _, g in par.iterrows())) if n else "Sin partidos.")
                 + ("\nBoleto actual: " + "; ".join(f"{l['mercado']} ({l['partido']}, modelo {l['prob']:.0%}, cuota {l['cuota']})" for l in ss.parlay) if ss.parlay else "\nBoleto vacío."))

# ================================================================== ARMAR / ANALIZAR (comparten partido y metrica)
else:
    local, visitante = selector_partido()
    partido = f"{local} vs {visitante} ({LIGA})"
    met = st.pills("Métrica", list(mo.METRICAS), format_func=lambda x: NOM[x], default=ss.get("met", "goles"),
                   label_visibility="collapsed", key="met_w") or "goles"
    ss.met = met
    var = incert(ss.liga, met)
    r = mo.analizar(df, local, visitante, met, inc=var)
    lam_l, lam_v = r["lambda_local"], r["lambda_visitante"]
    (ll, lh), (vl, vh) = r["rango"]["lam_l"], r["rango"]["lam_v"]      # rangos bajo-alto de las λ
    tl, th = ll + vl, lh + vh
    vol = {local: var.loc[local, "estado_casa"] == "volátil", visitante: var.loc[visitante, "estado_fuera"] == "volátil"}
    ml = mo.medias_liga(df, met)

    key_cfg = f"cfg_{met}_{local}_{visitante}"
    if key_cfg not in ss:
        ss[key_cfg] = {"Total": [centro_defecto(lam_l + lam_v, met), 2 if met == "goles" else 1],
                       local: [centro_defecto(lam_l, met), 1], visitante: [centro_defecto(lam_v, met), 1]}
    cfg = ss[key_cfg]
    lst = mercados(r, met, local, visitante, cfg)
    grupos = list(dict.fromkeys(x["grupo"] for x in lst))
    tabla_esp = tabla_modelos(local, visitante, lam_l, lam_v, r["rango"]["lam_l"], r["rango"]["lam_v"], ml, var)
    desc_esp = (f"Cuántos {NOM[met].lower()} espera el modelo para este partido (λ) y su rango de confianza del 80%. "
                f"Cuanto más angosto el rango, más seguro el número.")

    def selector_lineas(grp, key):
        if grp in ("Resultado", "Mayor número"):
            return
        a, b = st.columns([1, 1])
        centro = a.number_input(f"Línea {grp[:14]}", 0.5, 60.5, float(cfg[grp][0]), 1.0, key=f"c_{key}_{grp}")
        rango = b.selectbox("± líneas", [0, 1, 2, 3, 4], index=cfg[grp][1], key=f"r_{key}_{grp}")
        if [centro, rango] != cfg[grp]:
            cfg[grp] = [centro, rango]; st.rerun()

    def ev_html(mk, e, cuota):
        """Tarjeta de EV para una pata con la cuota de la casa: EV Poisson y EV pesimista + calificacion."""
        ev, ev_lo = mk["prob"] * cuota - 1, mk["lo"] * cuota - 1
        tiles = [("EV Poisson", ev, f'prob. {mk["prob"]:.0%} · justa {mo.cuota_justa(mk["prob"])}'),
                 ("EV pesimista", ev_lo, f'prob. {mk["lo"]:.0%}')]
        kpi = "".join(f'<div><div class="t">{nm}</div><div class="pct {"up" if v > 0 else "down"}">{v:+.2f}</div><div class="rg">{s}</div></div>' for nm, v, s in tiles)
        return (f'<div class="card flat" style="margin:4px 0"><div class="row" style="margin-bottom:8px"><div class="mid">{mk["mercado"]}</div>'
                f'<span class="tag {e["cls"]}">{e["tag"]}</span></div><div class="kpi esc">{kpi}</div></div>')

    # ---------------------------------------------------------- ARMAR
    if pagina == "Armar":
        if ss.parlay:
            rb = resumen_boleto(); prob, cuota, ev, plo, phi = rb; legs = ss.parlay
            f = kelly(plo, cuota)   # stake con la probabilidad pesimista: si aun asi hay valor, la apuesta aguanta
            sec("Stake sugerido", "Kelly calculado con la probabilidad pesimista del boleto: si con esa todavía hay valor, la apuesta aguanta un modelo "
                "demasiado optimista. Para parlays usa ¼ o ⅛ de Kelly.")
            a, b = st.columns([1, 1])
            ss.banca = a.number_input("Banca (Q)", 1.0, 1e9, float(ss.banca), 50.0, format="%.0f", help="Tu banca total en Q")
            b.markdown(f'<div class="card flat" style="margin:28px 0 0 0;padding:8px 12px"><div class="t">Boleto</div><div class="mid">cuota {cuota:.2f}</div><div class="rg">prob. pesimista {plo:.0%}</div></div>', unsafe_allow_html=True)
            if f <= 0:
                st.markdown('<div class="card flat"><div class="t">Con la probabilidad pesimista</div><div class="mid down">Sin valor: Kelly dice no apostar</div></div>', unsafe_allow_html=True)
            else:
                chips = "".join(f'<div><div class="t">{nm}</div><div class="pct">Q{ss.banca * f / d:,.0f}</div><div class="rg">{f / d:.1%}</div></div>'
                                for nm, d in (("Kelly", 1), ("½ Kelly", 2), ("¼ Kelly", 4), ("⅛ Kelly", 8)))
                st.markdown(f'<div class="kpi esc">{chips}</div>', unsafe_allow_html=True)
            with st.expander(f"Patas del boleto · {len(legs)} · pesimista {plo:.0%} (EV {plo * cuota - 1:+.2f}) · optimista {phi:.0%} (EV {phi * cuota - 1:+.2f})"):
                for i, l in enumerate(legs):
                    a, b = st.columns([6, 1])
                    a.markdown(f'<div class="row" style="padding:4px 0"><div class="c1"><div class="mid">{l["mercado"]}</div>'
                               f'<div class="small">{l["partido"]} · {l["metrica"]} · Poisson {l["prob"]:.0%}' + (f' ({l["lo"]:.0%}–{l["hi"]:.0%})' if "lo" in l else '') + f' · justa {mo.cuota_justa(l["prob"])} · casa {l["cuota"]:.2f}</div></div>'
                               f'<span class="tag {l["cls"]}">{l["cal"]}</span></div>', unsafe_allow_html=True)
                    if b.button("✕", key=f"del{i}"):
                        legs.pop(i); st.rerun()
                if len({l["partido"] for l in legs}) < len(legs):
                    st.caption("Patas del mismo partido no son independientes; la probabilidad combinada real difiere.")
                if st.button("Vaciar boleto"):
                    ss.parlay = []; st.rerun()

        sec(f"Esperado por modelo · {NOM[met].lower()}", desc_esp)
        st.markdown(f'<div class="card">{tabla_esp}</div>', unsafe_allow_html=True)

        grp = st.pills("Grupo", grupos, default=ss.get("grp", grupos[0]) if ss.get("grp") in grupos else grupos[0],
                       label_visibility="collapsed", key=f"grp_w{ss.gen}") or grupos[0]
        ss.grp = grp
        selector_lineas(grp, "armar")
        a, b = st.columns([1, 1])
        n = a.selectbox("Validar con", [3, 5, 8, 10, 15, 20], index=1, format_func=lambda x: f"validar últ. {x}", label_visibility="collapsed")
        solo = b.toggle("Solo Buena o mejor", value=False)
        hl, hv = historial(local, met, n), historial(visitante, met, n)

        sec(f"Mercados · {grp}", f"Probabilidad de cada mercado según el modelo y en cuántos de los últimos {n} partidos de cada equipo se habría cumplido "
            f"({local} · {visitante}). Calificación = 60% probabilidad Poisson + 40% cumplimiento.")
        # libro de mercados: encabezado + una fila por mercado con columnas fijas (mercado · Poisson · calificacion)
        html = (f'<div class="card"><div class="lg-h"><div class="c1 t">Mercado</div><div class="cn t">Poisson</div>'
                '<div class="cq t">Calificación</div></div>')
        filas_n = 0
        for mk in lst:
            if mk["grupo"] != grp: continue
            e = evaluar(mk, hl, hv, vol)
            if solo and e["cls"] not in ("exc", "bue"): continue
            filas_n += 1
            html += (f'<div class="mk"><div class="lg-r"><div class="c1"><div class="mid">{mk["mercado"]}</div><div class="small">justa <span class="w">{mo.cuota_justa(mk["prob"]):.2f}</span></div></div>'
                     f'<div class="cn"><div class="pct">{mk["prob"]:.0%}</div><div class="rg">{mk["lo"]:.0%}–{mk["hi"]:.0%}</div></div>'
                     f'<div class="cq"><span class="tag {e["cls"]}">{e["tag"]}</span><div class="rg" style="margin-top:3px">{e["hl"]}/{e["nl"]} · {e["hv"]}/{e["nv"]}</div></div></div>'
                     f'{barra(mk["prob"], e["tasa"], 1, P["ok"] if mk["prob"] >= 0.6 else P["warn"])}</div>')
        if not filas_n:
            html += '<div class="mk small">Ningún mercado con calificación Buena o mejor en este grupo. Quita el filtro o cambia de línea.</div>'
        html += nota("Barra = probabilidad Poisson; marca vertical = % de cumplimiento histórico. Bajo cada % va su rango pesimista–optimista. "
                     "Bajo la calificación, los aciertos de cada equipo. ↕ equipo volátil baja un nivel la calificación.")
        st.markdown(html + '</div>', unsafe_allow_html=True)
        ss.ctx_titulo = f"Armar · {partido} · {NOM[met]} · {grp}"
        ss.ctx_ia = (f"Vista: Armar. Liga {LIGA}. Partido {partido}. Métrica {NOM[met]}. λ local {lam_l:.2f} (rango bajo-alto {ll:.2f}-{lh:.2f}, "
                     f"varianza {var.loc[local, 'estado_casa']} {var.loc[local, 'ratio_casa']:.1f}x la liga, {var.loc[local, 'n_ef_casa']:.0f} partidos efectivos en casa), "
                     f"λ visitante {lam_v:.2f} ({vl:.2f}-{vh:.2f}, {var.loc[visitante, 'estado_fuera']} {var.loc[visitante, 'ratio_fuera']:.1f}x, {var.loc[visitante, 'n_ef_fuera']:.0f} fuera), "
                     f"λ total {lam_l + lam_v:.2f} ({tl:.2f}-{th:.2f}); media liga local {ml['local']:.2f}, visita {ml['visitante']:.2f}, total {ml['total']:.2f}. "
                     f"El rango es el intervalo del 80% del promedio del equipo (t de Student, desv/raíz(n)): incertidumbre de la λ, no la varianza Poisson. "
                     f"Validación con últimos {n} partidos.\n"
                     "Mercados del grupo " + grp + ":\n" + "\n".join(
                         f"- {mk['mercado']}: prob Poisson {mk['prob']:.0%} (pesimista {mk['lo']:.0%}, optimista {mk['hi']:.0%})"
                         f", cuota justa {mo.cuota_justa(mk['prob'])}, {local} cumplió {ev_['hl']}/{ev_['nl']}, {visitante} {ev_['hv']}/{ev_['nv']}, "
                         f"calificación {ev_['tag']}"
                         for mk in lst if mk["grupo"] == grp for ev_ in [evaluar(mk, hl, hv, vol)]) +
                     ("\nBoleto actual: " + "; ".join(f"{l['mercado']} ({l['partido']}, {l['metrica']}, modelo {l['prob']:.0%}, cuota casa {l['cuota']})" for l in ss.parlay)
                      if ss.parlay else "\nBoleto vacío."))

        sec("Agregar al boleto", "Elige el mercado, escribe la cuota que paga la casa y revisa el EV antes de agregar. EV = probabilidad × cuota − 1.")
        nombres = [x["mercado"] for x in lst if x["grupo"] == grp]
        a, b = st.columns([3, 2])
        sel = a.selectbox("Mercado", nombres, key=f"sel_{met}_{grp}", label_visibility="collapsed")
        cuota = b.number_input("Cuota casa", 1.01, 50.0, 1.90, 0.01, key=f"cuota_{met}_{grp}", label_visibility="collapsed")
        mk = next(x for x in lst if x["mercado"] == sel); e = evaluar(mk, hl, hv, vol)
        st.markdown(ev_html(mk, e, cuota), unsafe_allow_html=True)
        a, b = st.columns(2)
        if a.button("Agregar al boleto", width="stretch"):
            ss.parlay.append({"partido": partido, "metrica": NOM[met], "mercado": sel, "prob": mk["prob"], "cuota": cuota,
                              "cal": e["tag"], "cls": e["cls"], "lo": mk["lo"], "hi": mk["hi"]})
            registrar_uso("pata", f"{partido} | {sel} @ {cuota}")
            st.rerun()
        if b.button("Analizar esta pata", width="stretch"):
            ss.an_mercado, ss.grp = sel, grp
            ir_a("Analizar")

    # ---------------------------------------------------------- ANALIZAR
    else:
        grp = st.pills("Grupo", grupos, default=ss.get("grp", grupos[0]) if ss.get("grp") in grupos else grupos[0],
                       label_visibility="collapsed", key=f"grp_an{ss.gen}") or grupos[0]
        ss.grp = grp
        selector_lineas(grp, "an")
        nombres = [x["mercado"] for x in lst if x["grupo"] == grp]
        idx = nombres.index(ss.an_mercado) if ss.get("an_mercado") in nombres else 0
        sel = st.selectbox("Pata", nombres, index=idx, key=f"an_{met}_{grp}{ss.gen}", label_visibility="collapsed")
        mk = next(x for x in lst if x["mercado"] == sel)

        a, b = st.columns([3, 2])
        n = a.slider("Últimos N partidos", 3, 30, 10)
        filtro = b.selectbox("Condición", ["Todos", "Como jugarán"], label_visibility="collapsed",
                             help="Como jugarán = solo partidos del local en casa y del visitante fuera")
        cond_l, cond_v = ("Casa", "Fuera") if filtro != "Todos" else (None, None)
        hl, hv = historial(local, met, n, cond_l), historial(visitante, met, n, cond_v)
        e = evaluar(mk, hl, hv, vol)

        # tarjeta de veredicto: Poisson · histórico en grande, luego escenarios Poisson y esperado por modelo
        sec("Veredicto", f"Probabilidad de la pata según el modelo y en cuántos de los últimos {n} partidos de los dos equipos se cumplió. "
            "Calificación = 60% probabilidad Poisson + 40% cumplimiento histórico; ↕ equipo volátil la baja un nivel.")
        trio = (f'<div><div class="big">{mk["prob"]:.0%}</div><div class="t">Poisson</div><div class="rg">justa {mo.cuota_justa(mk["prob"]):.2f}</div></div>'
                f'<div><div class="big">{e["tasa"]:.0%}</div><div class="t">Histórico</div><div class="rg">{e["hl"] + e["hv"]} de {e["nl"] + e["nv"]} partidos</div></div>')
        st.markdown(f'<div class="card"><div class="row"><div class="c1"><div class="mid">{sel}</div><div class="small">{NOM[met]} · {partido}</div></div><span class="tag {e["cls"]}">{e["tag"]}</span></div>'
                    f'<div class="trio">{trio}</div>{barra(mk["prob"], e["tasa"], 1, P["acc"])}'
                    f'<div class="rg" style="margin-bottom:4px">barra = probabilidad Poisson · marca vertical = % histórico</div>'
                    f'<div class="sec"><div class="t">Escenarios Poisson · la misma pata con la λ pesimista y la optimista de cada equipo</div>{escenarios_html(mk)}</div>'
                    f'<div class="sec"><div class="t">Esperado por modelo · {NOM[met].lower()}</div>{tabla_esp}</div></div>',
                    unsafe_allow_html=True)

        def bloque(nombre, h, hits_, lado, color):
            col = mk["col_l"] if lado == "l" else mk["col_v"]
            ref_f, ref_c = (ml["local"], ml["visitante"]) if lado == "l" else (ml["visitante"], ml["local"])
            que = {"a_favor": "a favor", "en_contra": "en contra", "total": "total"}.get(col, sel)
            ref_chart = {"a_favor": ref_f, "en_contra": ref_c}.get(col, ml["total"])
            if col in ("a_favor", "en_contra", "total"):
                chart = chart_barras(h, col, mk["linea"], ref_chart, mk["over"], color)
                sub = f"{NOM[met].lower()} {que} por partido · barra de color = cumplió la pata"
            else:
                chart = chart_barras(h, "total", ml["total"], ml["total"], True, color)
                sub = f"{NOM[met].lower()} total por partido · barra de color = sobre la media de la liga"
            return (f'<div class="card"><div class="row"><div class="mid">{eq(nombre, lado)}</div>'
                    f'<div><span class="pct">{hits_}/{len(h)}</span> <span class="small">cumplió</span></div></div>'
                    f'{chart}<div class="rg">{sub} · antiguo → reciente · C casa / F fuera</div>'
                    f'<div style="margin-top:10px">{tabla_stats(h, mk["linea"], mk["over"], ref_f, ref_c, ml["total"])}</div></div>')

        sec("Historial por equipo", f"Últimos {n} partidos de cada uno" + (" (local en casa, visitante fuera)" if filtro != "Todos" else "")
            + ". Línea blanca punteada = línea del mercado; naranja = media de la liga. Debajo, media, mediana y desviación (qué tanto varía de partido a partido).")
        st.markdown(bloque(local, hl, e["hl"], "l", P["acc"]) + bloque(visitante, hv, e["hv"], "v", COLOR_VIS), unsafe_allow_html=True)
        def _st(h):
            return (f"a favor media {h.a_favor.mean():.1f} mediana {h.a_favor.median():.1f} desv {h.a_favor.std(ddof=0):.1f}; "
                    f"en contra media {h.en_contra.mean():.1f}; total media {h.total.mean():.1f} máx {h.total.max()} mín {h.total.min()}") if len(h) else "sin partidos"
        ss.ctx_titulo = f"Analizar · {partido} · {sel}"
        ss.ctx_ia = (f"Vista: Analizar. Liga {LIGA}. Partido {partido}. Métrica {NOM[met]}. Pata: {sel}. Prob modelo (Poisson) {mk['prob']:.0%} "
                     f"(pesimista {mk['lo']:.0%}, optimista {mk['hi']:.0%}; Poisson con la λ del extremo en contra / a favor). "
                     f"Varianza vs liga: {local} {var.loc[local, 'estado_casa']} {var.loc[local, 'ratio_casa']:.1f}x en casa, {visitante} {var.loc[visitante, 'estado_fuera']} {var.loc[visitante, 'ratio_fuera']:.1f}x fuera"
                     f", cuota justa {mo.cuota_justa(mk['prob'])}, calificación {e['tag']}, cumplimiento histórico {e['tasa']:.0%} ({e['hl']}/{e['nl']} {local}, {e['hv']}/{e['nv']} {visitante}) "
                     f"en últimos {n} partidos, filtro {filtro}. λ {local} {lam_l:.2f} (rango 80% {ll:.2f}-{lh:.2f}), λ {visitante} {lam_v:.2f} ({vl:.2f}-{vh:.2f}), media liga local {ml['local']:.2f} visita {ml['visitante']:.2f} total {ml['total']:.2f}.\n"
                     f"{local} últimos {len(hl)}: {_st(hl)}. Resultados (reciente→antiguo): " + ", ".join(f"{r_.condicion[0]} vs {r_.rival} {r_.marcador} ({int(r_.a_favor)}-{int(r_.en_contra)} {NOM[met].lower()})" for _, r_ in hl.iterrows()) +
                     f"\n{visitante} últimos {len(hv)}: {_st(hv)}. Resultados: " + ", ".join(f"{r_.condicion[0]} vs {r_.rival} {r_.marcador} ({int(r_.a_favor)}-{int(r_.en_contra)} {NOM[met].lower()})" for _, r_ in hv.iterrows()) +
                     ("\nBoleto actual: " + "; ".join(f"{l['mercado']} ({l['partido']}, modelo {l['prob']:.0%}, cuota {l['cuota']})" for l in ss.parlay) if ss.parlay else "\nBoleto vacío."))

        with st.expander("Partido a partido", expanded=True):
            st.markdown(lista_partidos(local, hl, mk, "l") + lista_partidos(visitante, hv, mk, "v"), unsafe_allow_html=True)
        with st.expander("Qué dice el modelo", expanded=False):
            if met in GOL and mk["grupo"] in ("Resultado", "Total"):
                st.markdown(f'<div class="card">{matriz_html(r["matriz"], local, visitante, mk["region"])}</div>', unsafe_allow_html=True)
            elif mk["grupo"] == "Mayor número":
                st.markdown(f'<div class="card">{diferencia_html(r["matriz"], mk, local, visitante, NOM[met].lower())}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="card">{distribucion_html(r["matriz"], mk, NOM[met].lower() + (" total" if mk["grupo"] == "Total" else " " + mk["grupo"]))}</div>',
                            unsafe_allow_html=True)

        sec("Agregar al boleto", "Escribe la cuota que paga la casa y revisa el EV antes de agregar. Al agregar vuelves a Armar.")
        cuota = st.number_input("Cuota casa", 1.01, 50.0, 1.90, 0.01, key=f"cuota_an_{met}", label_visibility="collapsed")
        st.markdown(ev_html(mk, e, cuota), unsafe_allow_html=True)
        if st.button("Agregar al boleto", width="stretch", key="add_an"):
            ss.parlay.append({"partido": partido, "metrica": NOM[met], "mercado": sel, "prob": mk["prob"], "cuota": cuota,
                              "cal": e["tag"], "cls": e["cls"], "lo": mk["lo"], "hi": mk["hi"]})
            registrar_uso("pata", f"{partido} | {sel} @ {cuota}")
            ss.grp = grp
            ir_a("Armar")

# ================================================================== analista IA flotante (boton pequeno abajo a la izquierda)
st.markdown(f"""<style>
  div[data-testid="stPopover"] {{position:fixed; bottom:16px; left:12px; z-index:1000; width:auto !important;}}
  div[data-testid="stPopover"] > div {{width:auto !important;}}
  div[data-testid="stPopover"] button {{width:50px !important; height:50px !important; min-height:50px; border-radius:50% !important; padding:0 !important;
      background:{P['acc']} !important; color:#fff !important; border:none !important; font-weight:800; font-size:0.8rem; box-shadow:0 6px 18px rgba(0,0,0,.4);}}
  div[data-testid="stPopover"] button p {{font-size:0.8rem; font-weight:800;}}
  div[data-testid="stPopover"] button svg {{display:none;}}
  div[data-testid="stPopoverBody"] {{width:min(94vw, 440px); max-height:75vh; overflow:auto;}}
  .msg {{padding:8px 11px; border-radius:12px; margin:5px 0; font-size:0.84rem; line-height:1.4;}}
  .msg.u {{background:{P['acc']}; color:#fff; margin-left:15%;}} .msg.a {{background:{P['card2']}; color:{P['txt']}; margin-right:6%;}}
</style>""", unsafe_allow_html=True)
with st.popover("IA"):
    ss.setdefault("ctx_titulo", "")
    st.markdown(f'<div class="mid">Analista Kuota</div><div class="small">{ss.ctx_titulo or "abre Armar o Analizar para darle contexto"}</div>', unsafe_allow_html=True)
    for m in ss.chat[-8:]:
        st.markdown(f'<div class="msg {"u" if m["rol"] == "user" else "a"}">{m["txt"]}</div>', unsafe_allow_html=True)
    sug = st.pills("Sugerencias", ["¿Qué opinas de esta pata?", "Debate mi parlay", "¿Mayor riesgo?"], label_visibility="collapsed", key=f"sug{len(ss.chat)}")
    preg = st.text_input("Pregunta", key=f"ia_q{len(ss.chat)}", placeholder="Escribe tu pregunta…", label_visibility="collapsed")
    a, b = st.columns([3, 1])
    enviar = a.button("Enviar", width="stretch", key="ia_send")
    texto = (preg.strip() if enviar and preg.strip() else None) or (sug if not enviar else None)
    if texto:
        ss.chat.append({"rol": "user", "txt": texto})
        ss.chat.append({"rol": "assistant", "txt": preguntar_ia(texto)})
        registrar_uso("ia", texto[:80])
        st.rerun()
    if b.button("Limpiar", width="stretch", key="ia_clear"):
        ss.chat = []; st.rerun()

st.markdown(f'<div class="note" style="margin-top:18px">{LIGA}: {len(df)} partidos cargados, último el {df["fecha"].max():%d/%m/%Y}. '
            f'Fuente: {"ESPN" if ss.liga == "ligamx" else "football-data.co.uk"}. Los términos de la app están explicados en el Diccionario.</div>', unsafe_allow_html=True)
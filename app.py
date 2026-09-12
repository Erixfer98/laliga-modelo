"""
app.py — Sports Book La Liga.
Paginas: Inicio · Armar · Analizar · Tabla · Admin (solo administradores).
Usuarios y registro de uso: opcionales, se configuran en Streamlit Cloud -> Settings -> Secrets (ver pagina Admin).
Local: streamlit run app.py
"""

import base64
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st

import modelo as mo

st.set_page_config(page_title="Sports Book", page_icon="⚽", layout="centered", initial_sidebar_state="collapsed")

# ------------------------------------------------------------------ tema (sigue el tema de Streamlit: claro u oscuro)
try:
    TEMA = st.context.theme.type or "dark"
except Exception:
    TEMA = "dark"
P = {"dark": dict(card="#16181d", card2="#1e2128", txt="#f2f2f2", mut="#8b919a", line="#262a32", line2="#20242b",
                  barbg="#262a32", miss="#2f343d", mark="#ffffff", app="#0b0c0f", ok="#22c55e", bad="#f05252", acc="#3b82f6"),
     "light": dict(card="#ffffff", card2="#f4f5f7", txt="#111318", mut="#5b6270", line="#e3e5ea", line2="#eceef2",
                   barbg="#e3e5ea", miss="#c9cdd4", mark="#111318", app="#f7f8fa", ok="#15803d", bad="#c62828", acc="#2563eb")}[TEMA]

st.markdown(f"""
<style>
  .block-container {{padding: 3rem 0.9rem 4rem 0.9rem; max-width: 640px;}}
  h3 {{font-weight:700; letter-spacing:-.01em;}}
  .card {{background:{P['card']}; border:1px solid {P['line']}; border-radius:16px; padding:14px 16px; margin:10px 0; color:{P['txt']};}}
  .card.flat {{background:{P['card2']}; border:none;}}
  .t {{font-size:0.7rem; color:{P['mut']}; text-transform:uppercase; letter-spacing:.08em; font-weight:600;}}
  .row {{display:flex; justify-content:space-between; align-items:center; gap:10px;}}
  .big {{font-size:1.75rem; font-weight:700; line-height:1.1; letter-spacing:-.02em;}}
  .mid {{font-size:1rem; font-weight:600;}}
  .small {{font-size:0.78rem; color:{P['mut']};}}
  .w {{color:{P['txt']}; font-weight:600;}}
  .bar {{height:6px; border-radius:3px; background:{P['barbg']}; position:relative; margin:6px 0 3px 0;}}
  .bar > div {{height:6px; border-radius:3px;}}
  .bar .mark {{position:absolute; top:-3px; width:2px; height:12px; background:{P['mark']}; opacity:.9;}}
  .mk {{border-top:1px solid {P['line2']}; padding:10px 0;}}
  .mk:first-child {{border-top:none;}}
  .tag {{display:inline-block; padding:3px 9px; border-radius:999px; font-size:0.7rem; font-weight:700; white-space:nowrap; letter-spacing:.02em;}}
  .exc {{background:#14532d; color:#bbf7d0;}} .bue {{background:#166534; color:#dcfce7;}} .reg {{background:#78350f; color:#fde68a;}}
  .mal {{background:#7f1d1d; color:#fecaca;}} .pes {{background:#450a0a; color:#fca5a5;}}
  .up {{color:{P['ok']};}} .down {{color:{P['bad']};}}
  .sticky {{position:sticky; top:0; z-index:99; background:{P['app']}; padding:4px 0;}}
  table.st {{width:100%; border-collapse:collapse; font-size:0.82rem; color:{P['txt']};}}
  table.st th {{text-align:right; font-weight:500; color:{P['mut']}; padding:6px 4px; border-bottom:1px solid {P['line']};}}
  table.st th:first-child, table.st td:first-child {{text-align:left; color:{P['mut']};}}
  table.st td {{text-align:right; padding:6px 4px; border-bottom:1px solid {P['line2']};}}
  table.st tr.liga td {{color:{P['mut']}; font-style:italic;}}
  table.st tr.me td {{background:{P['card2']}; font-weight:600;}}
  table.mx {{border-collapse:separate; border-spacing:3px; width:100%; font-size:0.78rem;}}
  table.mx td {{text-align:center; padding:6px 0; border-radius:6px; color:{P['txt']};}}
  table.mx th {{font-size:0.72rem; color:{P['mut']}; font-weight:500; padding:2px;}}
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
  .pl .sc {{width:46px; flex:none; text-align:center; font-weight:700; border-radius:6px; padding:4px 0; color:#fff; font-size:0.8rem; letter-spacing:.03em;}}
  .sc.g {{background:{P['ok']};}} .sc.p {{background:{P['bad']};}} .sc.e {{background:#6b7280;}}
  .pl .mv {{width:54px; flex:none; text-align:right; line-height:1.1;}}
  .pl .mv b {{font-size:1rem;}} .pl .mv .small {{font-size:0.62rem;}}
  .mv.ok b {{color:{P['ok']};}} .mv.no b {{color:{P['mut']};}}
  .forma {{display:inline-flex; gap:3px; vertical-align:middle;}}
  .forma span {{width:18px; height:18px; border-radius:50%; font-size:0.62rem; font-weight:700; color:#fff; display:inline-flex; align-items:center; justify-content:center;}}
  .forma .g {{background:{P['ok']};}} .forma .p {{background:{P['bad']};}} .forma .e {{background:#6b7280;}}
  .tb {{display:flex; align-items:center; gap:8px; padding:8px 0; border-bottom:1px solid {P['line2']}; font-size:0.84rem;}}
  .tb:last-child {{border-bottom:none;}}
  .tb .pos {{width:22px; text-align:center; color:{P['mut']}; font-weight:600;}}
  .tb .eq {{flex:1; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}}
  .tb .n {{width:26px; text-align:center; color:{P['mut']};}} .tb .pts {{width:30px; text-align:right; font-weight:700;}}
  .tb .z {{width:3px; height:26px; border-radius:2px;}}
  .kpi {{display:flex; gap:8px;}} .kpi > div {{flex:1; background:{P['card2']}; border-radius:12px; padding:10px 12px;}}
</style>""", unsafe_allow_html=True)


LIGAS = {"laliga": "La Liga", "premier": "Premier League", "seriea": "Serie A", "bundesliga": "Bundesliga", "ligue1": "Ligue 1"}
LIGAS_DISPONIBLES = {k: v for k, v in LIGAS.items() if os.path.exists(f"datos/bbdd_{k}.csv")} or {"laliga": "La Liga"}


@st.cache_data(ttl=3600)
def datos(liga):
    return mo.cargar(f"datos/bbdd_{liga}.csv")


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
NOM = mo.NOMBRES
HORA_GT = ZoneInfo("America/Guatemala")


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


SISTEMA_IA = ("Eres el analista de Sports Book La Liga, una app de apuestas con un modelo Poisson/Dixon-Coles y estadísticas descriptivas. "
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
    try:
        r = requests.post(c["url"], headers={"Authorization": f"Bearer {c['key']}", "Content-Type": "application/json"},
                          json={"model": c["modelo"], "messages": msgs, "temperature": 0.4, "max_tokens": 600}, timeout=60)
        if r.status_code != 200:
            return f"Error {r.status_code}: {r.text[:200]}"
        return r.json()["choices"][0]["message"]["content"].strip()
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
if usuarios and "usuario" not in ss:
    st.markdown("### Sports Book")
    st.markdown('<div class="card"><div class="t">Acceso</div><div class="small">Ingresa con tu usuario y contraseña.</div></div>', unsafe_allow_html=True)
    u = st.text_input("Usuario")
    c = st.text_input("Contraseña", type="password")
    if st.button("Entrar", width="stretch"):
        if u in usuarios and str(usuarios[u]) == c:
            ss.usuario = u
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


def evaluar(mk, hl, hv):
    cl, cv = cumple(hl, mk, "l"), cumple(hv, mk, "v")
    n = len(hl) + len(hv)
    tasa = (cl.sum() + cv.sum()) / n if n else 0
    txt, cls = calificar(mk["prob"], tasa)
    return {"hl": int(cl.sum()), "nl": len(hl), "hv": int(cv.sum()), "nv": len(hv), "tasa": tasa, "cal": txt, "cls": cls,
            "serie_l": cl, "serie_v": cv}


# ================================================================== mercados (linea configurable)
def lineas(centro, rango):
    return [x for x in np.arange(centro - rango, centro + rango + 0.01, 1.0) if x > 0]


def mercados(r, met, local, visitante, cfg):
    """cfg = {grupo: (centro, rango)}. Devuelve lista de mercados con su regla de evaluacion historica."""
    m, lam_l, lam_v = r["matriz"], r["lambda_local"], r["lambda_visitante"]
    k = m.shape[0]; tot = np.add.outer(np.arange(k), np.arange(k))
    out = []

    def add(nombre, grupo, p, col_l, col_v, linea, over, region):
        out.append({"mercado": nombre, "grupo": grupo, "prob": float(min(max(p, 0), 1)), "col_l": col_l, "col_v": col_v,
                    "linea": linea, "over": over, "region": region})

    if met in GOL:
        p1, px, p2 = np.tril(m, -1).sum(), np.trace(m), np.triu(m, 1).sum()
        add(f"Gana {local}", "Resultado", p1, "gano", "perdio", 0.5, True, lambda x, y: x > y)
        add("Empate", "Resultado", px, "empato", "empato", 0.5, True, lambda x, y: x == y)
        add(f"Gana {visitante}", "Resultado", p2, "perdio", "gano", 0.5, True, lambda x, y: x < y)
        add(f"{local} o empate", "Resultado", p1 + px, "no_perdio", "no_gano", 0.5, True, lambda x, y: x >= y)
        add(f"{visitante} o empate", "Resultado", p2 + px, "no_gano", "no_perdio", 0.5, True, lambda x, y: x <= y)
        b = m[1:, 1:].sum()
        add("Ambos anotan: Sí", "Resultado", b, "btts", "btts", 0.5, True, lambda x, y: x > 0 and y > 0)
        add("Ambos anotan: No", "Resultado", 1 - b, "btts", "btts", 0.5, False, lambda x, y: x == 0 or y == 0)
    for ln in lineas(*cfg["Total"]):
        po = m[tot > ln].sum()
        add(f"Total Over {ln}", "Total", po, "total", "total", ln, True, lambda x, y, ln=ln: x + y > ln)
        add(f"Total Under {ln}", "Total", 1 - po, "total", "total", ln, False, lambda x, y, ln=ln: x + y < ln)
    for ln in lineas(*cfg[local]):
        po = mo.prob_over(lam_l, ln)
        add(f"{local} Over {ln}", local, po, "a_favor", "en_contra", ln, True, lambda x, y, ln=ln: x > ln)
        add(f"{local} Under {ln}", local, 1 - po, "a_favor", "en_contra", ln, False, lambda x, y, ln=ln: x < ln)
    for ln in lineas(*cfg[visitante]):
        po = mo.prob_over(lam_v, ln)
        add(f"{visitante} Over {ln}", visitante, po, "en_contra", "a_favor", ln, True, lambda x, y, ln=ln: y > ln)
        add(f"{visitante} Under {ln}", visitante, 1 - po, "en_contra", "a_favor", ln, False, lambda x, y, ln=ln: y < ln)
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
            f'<div class="ln" style="bottom:{linea / mx * 100:.0f}%"><span>línea {linea}</span></div>'
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
    return (f'<div class="card"><div class="row"><div class="mid">{equipo}</div>'
            f'<div class="small">{G}G {E}E {Pp}P</div></div>'
            f'<div class="row" style="margin:4px 0 6px 0"><div class="forma">{dots}</div>'
            f'<div class="small">{NOM[met].lower()} {que} · <span class="w">{int(serie.sum())}/{len(h)}</span> cumplió</div></div>'
            f'{filas}<div class="small" style="margin-top:6px">racha: antiguo → reciente · marcador verde = ganó, rojo = perdió, gris = empate · valor verde = cumplió la pata</div></div>')


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
    return h + f'</table><div class="small" style="margin-top:4px">filas = {local} · columnas = {visitante} · cifra = % modelo · verde = marcador con el que gana la pata, gris = no gana · más intenso = más probable</div>'


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
    return f'<div class="chart"><div class="bars">{bars}</div></div><div class="small">{etiqueta} según el modelo · verde = gana la pata</div>'



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
         + ('' if compacta else '<div class="n t" style="width:44px">GF-GC</div>') + '<div class="n t">DG</div><div class="pts t">PTS</div>'
         + ('' if compacta else '<div class="forma" style="width:102px"></div>') + '</div>')
    for i, f in t.iterrows():
        pos = i + 1
        z = P["ok"] if pos <= 4 else ("#f59e0b" if pos <= 6 else (P["bad"] if pos > n - 3 else "transparent"))
        forma = "".join(f'<span class="{x}">{x.upper()}</span>' for x in f.forma[-5:])
        h += (f'<div class="tb"{" style=background:" + P["card2"] if f.equipo in resaltar else ""}><div class="z" style="background:{z}"></div>'
              f'<div class="pos">{pos}</div><div class="eq">{f.equipo}</div><div class="n">{f.J}</div><div class="n">{f.G}</div>'
              f'<div class="n">{f.E}</div><div class="n">{f.P}</div>' + ('' if compacta else f'<div class="n" style="width:44px">{f.GF}-{f.GC}</div>')
              + f'<div class="n">{f.DG:+d}</div><div class="pts">{f.PTS}</div>' + ('' if compacta else f'<div class="forma" style="width:102px">{forma}</div>') + '</div>')
    return h + '<div class="small" style="margin-top:6px">verde = Champions · ámbar = Europa · rojo = descenso · forma: antiguo → reciente</div></div>'


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


# ================================================================== navegacion
paginas = ["Inicio", "Armar", "Analizar", "Tabla", "Diccionario"] + (["Admin"] if ES_ADMIN else [])
top1, top2 = st.columns([3, 1])
top1.markdown("### Sports Book")
if usuarios:
    if top2.button(f"Salir · {ss.usuario}", width="stretch"):
        registrar_uso("logout")
        for k in list(ss.keys()):
            del ss[k]
        st.rerun()
else:
    top2.markdown(f'<div class="small" style="text-align:right;padding-top:14px">{ss.usuario}</div>', unsafe_allow_html=True)
pagina = st.segmented_control("Página", paginas, default=ss.pagina if ss.pagina in paginas else "Inicio",
                              label_visibility="collapsed", key=f"pag_w{ss.gen}") or ss.pagina
ss.pagina = pagina
if pagina not in ("Diccionario", "Admin"):
    liga_sel = st.pills("Liga", list(LIGAS_DISPONIBLES), format_func=lambda k: LIGAS_DISPONIBLES[k], default=ss.liga,
                        label_visibility="collapsed", key=f"liga_w{ss.gen}") or ss.liga
    if liga_sel != ss.liga:
        ss.liga = liga_sel; ss.gen += 1; st.rerun()
LIGA = LIGAS_DISPONIBLES[ss.liga]


def ir_a(pag):
    ss.pagina = pag; ss.gen += 1; st.rerun()


def resumen_boleto():
    """Devuelve (prob, cuota, ev) del boleto o None."""
    legs = ss.parlay
    if not legs:
        return None
    prob = float(np.prod([l["prob"] for l in legs])); cuota = float(np.prod([l["cuota"] for l in legs]))
    return prob, cuota, prob * cuota - 1


# ================================================================== PAGINA INICIO
if pagina == "Inicio":
    temp = temporada_actual()
    ult = df["fecha"].max()
    st.markdown(f'<div class="card flat"><div class="row"><div><div class="t">{LIGA} · temporada {temp}</div>'
                f'<div class="mid">{len(df[df.temporada_txt == temp])} partidos jugados</div></div>'
                f'<div style="text-align:right"><div class="t">Datos al</div><div class="mid">{ult:%d/%m/%Y}</div></div></div></div>',
                unsafe_allow_html=True)
    rb = resumen_boleto()
    if rb:
        prob, cuota, ev = rb
        st.markdown(f'<div class="card"><div class="row"><div><div class="t">Boleto en curso · {len(ss.parlay)} patas</div>'
                    f'<div class="mid">cuota {cuota:.2f} · modelo {prob:.0%}</div></div>'
                    f'<div class="big {"up" if ev > 0 else "down"}">EV {ev:+.2f}</div></div></div>', unsafe_allow_html=True)
    a, b = st.columns(2)
    if a.button("Armar parlay", width="stretch"):
        ir_a("Armar")
    if b.button("Analizar una pata", width="stretch"):
        ir_a("Analizar")

    t = tabla_posiciones(temp)
    st.markdown('<div class="t" style="margin-top:8px">Tabla · top 6</div>', unsafe_allow_html=True)
    st.markdown(html_tabla(t.head(6), compacta=True), unsafe_allow_html=True)
    ss.ctx_ia = (f"Vista: Inicio. Liga {LIGA}. Temporada {temp}, datos al {ult:%d/%m/%Y}. Tabla: " +
                 "; ".join(f"{i + 1}. {f.equipo} {f.PTS} pts (J{f.J} G{f.G} E{f.E} P{f.P}, DG {f.DG:+d})" for i, f in t.iterrows()) +
                 ("\nBoleto actual: " + "; ".join(f"{l['mercado']} ({l['partido']}, modelo {l['prob']:.0%}, cuota {l['cuota']})" for l in ss.parlay) if ss.parlay else "\nBoleto vacío."))

    st.markdown('<div class="t" style="margin-top:8px">Tendencias · últimos 5 partidos</div>', unsafe_allow_html=True)
    met_h = st.pills("Métrica tendencias", list(mo.METRICAS), format_func=lambda x: NOM[x], default="corners", label_visibility="collapsed")
    if met_h:
        tt, media = tendencias(met_h)
        def fila(f):
            return (f'<div class="mk"><div class="row"><div class="mid">{f.equipo}</div><div><span class="w">{f.prom:.1f}</span> '
                    f'<span class="small">{f.prom - media:+.1f} vs liga</span></div></div>'
                    f'{barra(f.prom, media, max(tt.prom.max(), media) * 1.1, P["ok"] if f.prom >= media else P["mut"])}'
                    f'<div class="small">a favor {f.favor:.1f} · en contra {f.contra:.1f}</div></div>')
        st.markdown(f'<div class="card"><div class="t">Más {NOM[met_h].lower()} por partido · media liga {media:.1f}</div>'
                    + "".join(fila(f) for _, f in tt.head(4).iterrows()) + '</div>'
                    f'<div class="card"><div class="t">Menos {NOM[met_h].lower()} por partido</div>'
                    + "".join(fila(f) for _, f in tt.tail(4).iloc[::-1].iterrows()) + '</div>', unsafe_allow_html=True)
        st.caption("Barra = promedio del equipo (a favor + en contra) en sus últimos 5 · marca blanca = media de la liga. "
                   "Sirve para elegir qué partido y mercado analizar.")

# ================================================================== PAGINA DICCIONARIO
elif pagina == "Diccionario":
    DIC = [
        ("Modelo", "λ (lambda)", "Cantidad esperada de la métrica para un equipo en este partido, según el modelo. Ej. λ corners 5.2 = se esperan unos 5 corners de ese equipo."),
        ("Modelo", "Poisson", "Fórmula que convierte una λ en probabilidades: cuántas veces sale 0, 1, 2, 3… Se usa para goles, tiros, corners, faltas y tarjetas."),
        ("Modelo", "Dixon-Coles (ρ)", "Corrección a Poisson solo para goles: ajusta los marcadores 0-0, 1-0, 0-1 y 1-1, que Poisson estima mal. ρ negativo = más empates bajos."),
        ("Modelo", "Ataque / defensa", "Fuerza del equipo relativa a la liga. 1.00 = promedio; 1.30 = produce 30% más que un equipo promedio; 0.80 = 20% menos."),
        ("Modelo", "Peso por recencia", "Los partidos recientes pesan más que los viejos al calcular las fuerzas. Un partido de hace ~140 días pesa la mitad que uno de hoy."),
        ("Modelo", "Matriz de resultados", "Tabla con la probabilidad de cada marcador exacto (filas = local, columnas = visitante). Verde = marcadores con los que gana la pata."),
        ("Mercados", "Cuota justa", "1 dividido entre la probabilidad del modelo. Es la cuota a la que no ganas ni pierdes a largo plazo. Si la casa paga más que la justa, hay valor."),
        ("Mercados", "EV (valor esperado)", "prob. modelo × cuota − 1. Positivo = a largo plazo ganas; negativo = pierdes. EV +0.10 = ganas 10 centavos por cada Q1 apostado, en promedio."),
        ("Mercados", "Over / Under", "Más de / menos de una línea. Total Over 2.5 goles = 3 o más goles en el partido. Las líneas .5 no permiten empate."),
        ("Mercados", "Línea y ± líneas", "Línea = el centro que quieres ver (ej. 9.5 corners). ± líneas = cuántas líneas alrededor mostrar (±2 con 9.5 muestra 7.5, 8.5, 9.5, 10.5 y 11.5)."),
        ("Mercados", "1X2 / doble oportunidad", "1 = gana local, X = empate, 2 = gana visitante. 1X = local o empate; X2 = visitante o empate."),
        ("Mercados", "Ambos anotan (BTTS)", "Sí = los dos equipos marcan al menos un gol. No = al menos uno se queda en cero."),
        ("Mercados", "Total / Local / Visitante", "Grupos de mercados. Total suma los dos equipos; Local y Visitante son la métrica de un solo equipo."),
        ("Validación", "Últ. N", "Contra cuántos partidos recientes de cada equipo se valida la pata. N chico = forma actual; N grande = tendencia estable."),
        ("Validación", "X/N cumplió", "En cuántos de los últimos N partidos del equipo se habría cumplido ese mercado. 4/5 = pasó en 4 de 5."),
        ("Validación", "Calificación", "60% probabilidad del modelo + 40% cumplimiento histórico. Excelente ≥ 78%, Buena ≥ 68%, Regular ≥ 56%, Mala ≥ 45%, Pésima el resto."),
        ("Validación", "Como jugarán", "Filtro: solo partidos del local jugando en casa y del visitante jugando fuera."),
        ("Validación", "Media / mediana / desv. est.", "Media = promedio. Mediana = valor del medio (resiste goleadas raras). Desviación estándar = qué tanto varía de partido a partido; alta = equipo irregular."),
        ("Validación", "Media liga", "Promedio de todos los partidos cargados. Referencia para saber si un equipo está por encima o por debajo de lo normal."),
        ("Banca", "Banca", "Dinero total destinado a apostar. Todo el stake se calcula como porcentaje de esto."),
        ("Banca", "Kelly", "Fracción de banca que maximiza el crecimiento si la probabilidad del modelo fuera exacta: ((cuota−1)·p − (1−p)) / (cuota−1). Nunca lo es, por eso existen las fracciones."),
        ("Banca", "½, ¼, ⅛ Kelly", "La mitad, un cuarto y un octavo del Kelly completo. Para parlays usa ¼ o ⅛: menos crecimiento pero mucha menos probabilidad de quebrar."),
        ("Banca", "Patas no independientes", "Dos patas del mismo partido (ej. gana Madrid + over 2.5) están relacionadas; multiplicar sus probabilidades da un número inexacto."),
        ("Datos", "Fuente", "football-data.co.uk. Se descarga cada lunes por GitHub Actions y regenera la base completa."),
        ("Datos", "Columnas _val", "goles, goles 1er/2do tiempo, tiros, tiros a puerta, corners, faltas, amarillas y rojas, cada una para local y visitante."),
        ("Datos", "Jornada", "Estimada: partido n-ésimo de cada equipo en la temporada. Un aplazado se cuenta cuando se jugó."),
        ("Datos", "Temporada", "Formato 2025-26 (agosto a mayo)."),
    ]
    q = st.text_input("Buscar", placeholder="Buscar un término…", label_visibility="collapsed").strip().lower()
    grupos_d = list(dict.fromkeys(g for g, _, _ in DIC))
    for g in grupos_d:
        items = [(t_, d_) for gg, t_, d_ in DIC if gg == g and (not q or q in t_.lower() or q in d_.lower())]
        if not items:
            continue
        st.markdown(f'<div class="t" style="margin-top:8px">{g}</div><div class="card">' +
                    "".join(f'<div class="mk"><div class="mid">{t_}</div><div class="small" style="margin-top:2px;color:{P["txt"]};opacity:.85">{d_}</div></div>' for t_, d_ in items)
                    + '</div>', unsafe_allow_html=True)

# ================================================================== PAGINA TABLA
elif pagina == "Tabla":
    temps = sorted(df.temporada_txt.unique(), reverse=True)
    temp = st.selectbox("Temporada", temps, label_visibility="collapsed")
    t = tabla_posiciones(temp)
    st.markdown(html_tabla(t), unsafe_allow_html=True)
    st.caption(f"{LIGA} · calculada desde la BBDD (solo partidos cargados). Zonas europeas y de descenso son orientativas (4 / 2 / 3).")

# ================================================================== PAGINA ADMIN
elif pagina == "Admin":
    st.markdown('<div class="t">Usuarios y uso</div>', unsafe_allow_html=True)
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

# ================================================================== ARMAR / ANALIZAR (comparten partido y metrica)
else:
    c1, c2 = st.columns(2)
    local = c1.selectbox("Local", lista, index=lista.index("Real Madrid") if "Real Madrid" in lista else 0)
    visitante = c2.selectbox("Visitante", [e for e in lista if e != local])
    partido = f"{local} vs {visitante} ({LIGA})"
    met = st.pills("Métrica", list(mo.METRICAS), format_func=lambda x: NOM[x], default=ss.get("met", "goles"),
                   label_visibility="collapsed", key="met_w") or "goles"
    ss.met = met
    r = mo.analizar(df, local, visitante, met)
    lam_l, lam_v = r["lambda_local"], r["lambda_visitante"]
    ml = mo.medias_liga(df, met)

    key_cfg = f"cfg_{met}_{local}_{visitante}"
    if key_cfg not in ss:
        ss[key_cfg] = {"Total": [centro_defecto(lam_l + lam_v, met), 2 if met == "goles" else 1],
                       local: [centro_defecto(lam_l, met), 1], visitante: [centro_defecto(lam_v, met), 1]}
    cfg = ss[key_cfg]
    lst = mercados(r, met, local, visitante, cfg)
    grupos = list(dict.fromkeys(x["grupo"] for x in lst))

    def selector_lineas(grp, key):
        if grp == "Resultado":
            return
        a, b = st.columns([1, 1])
        centro = a.number_input(f"Línea {grp[:14]}", 0.5, 60.5, float(cfg[grp][0]), 1.0, key=f"c_{key}_{grp}")
        rango = b.selectbox("± líneas", [0, 1, 2, 3, 4], index=cfg[grp][1], key=f"r_{key}_{grp}")
        if [centro, rango] != cfg[grp]:
            cfg[grp] = [centro, rango]; st.rerun()

    # ---------------------------------------------------------- ARMAR
    if pagina == "Armar":
        rb = resumen_boleto()
        if rb:
            prob, cuota, ev = rb; legs = ss.parlay
            st.markdown(f'<div class="sticky"><div class="card" style="margin:0"><div class="row">'
                        f'<div><div class="t">Boleto · {len(legs)} pata{"s" if len(legs) > 1 else ""}</div><div class="mid">cuota {cuota:.2f} · justa {mo.cuota_justa(prob)}</div></div>'
                        f'<div style="text-align:right"><div class="t">modelo {prob:.0%}</div><div class="big {"up" if ev > 0 else "down"}">EV {ev:+.2f}</div></div>'
                        f'</div></div></div>', unsafe_allow_html=True)
            f = kelly(prob, cuota)
            a, b = st.columns([1, 2])
            ss.banca = a.number_input("Banca", 1.0, 1e9, float(ss.banca), 50.0, format="%.0f", help="Tu banca total en Q")
            if f <= 0:
                b.markdown('<div class="card flat" style="margin:2px 0;padding:8px 12px"><div class="t">Stake sugerido</div>'
                           '<div class="mid down">Sin valor: Kelly dice no apostar este parlay</div></div>', unsafe_allow_html=True)
            else:
                chips = "".join(f'<div style="text-align:center"><div class="t">{nm}</div><div class="mid">Q{ss.banca * f / d:,.0f}</div>'
                                f'<div class="small">{f / d:.1%}</div></div>' for nm, d in (("Kelly", 1), ("½", 2), ("¼", 4), ("⅛", 8)))
                b.markdown(f'<div class="card flat" style="margin:2px 0;padding:8px 12px"><div class="t">Stake sugerido · banca Q{ss.banca:,.0f}</div>'
                           f'<div class="row" style="margin-top:4px">{chips}</div></div>', unsafe_allow_html=True)
            with st.expander("Ver patas del boleto"):
                for i, l in enumerate(legs):
                    a, b = st.columns([6, 1])
                    a.markdown(f'<div class="row" style="padding:4px 0"><div><div class="mid">{l["mercado"]}</div>'
                               f'<div class="small">{l["partido"]} · {l["metrica"]} · modelo {l["prob"]:.0%} · justa {mo.cuota_justa(l["prob"])} · casa {l["cuota"]:.2f}</div></div>'
                               f'<span class="tag {l["cls"]}">{l["cal"]}</span></div>', unsafe_allow_html=True)
                    if b.button("✕", key=f"del{i}"):
                        legs.pop(i); st.rerun()
                if len({l["partido"] for l in legs}) < len(legs):
                    st.caption("Patas del mismo partido no son independientes; la prob. combinada real difiere.")
                if st.button("Vaciar boleto"):
                    ss.parlay = []; st.rerun()

        st.markdown(f'<div class="card flat"><div class="t">{NOM[met]} · esperado del modelo</div>'
                    f'<div class="mid">{local} <span class="w">{lam_l:.2f}</span> · {visitante} <span class="w">{lam_v:.2f}</span> · total <span class="w">{lam_l + lam_v:.2f}</span></div>'
                    f'<div class="small">media liga: local {ml["local"]:.1f} · visita {ml["visitante"]:.1f} · total {ml["total"]:.1f}</div></div>',
                    unsafe_allow_html=True)

        grp = st.pills("Grupo", grupos, default=ss.get("grp", grupos[0]) if ss.get("grp") in grupos else grupos[0],
                       label_visibility="collapsed", key=f"grp_w{ss.gen}") or grupos[0]
        ss.grp = grp
        selector_lineas(grp, "armar")
        a, b = st.columns([1, 1])
        n = a.selectbox("Validar con", [3, 5, 8, 10, 15, 20], index=1, format_func=lambda x: f"validar últ. {x}", label_visibility="collapsed")
        solo = b.toggle("Solo Buena o mejor", value=False)
        hl, hv = historial(local, met, n), historial(visitante, met, n)

        html = '<div class="card">'
        for mk in lst:
            if mk["grupo"] != grp: continue
            e = evaluar(mk, hl, hv)
            if solo and e["cls"] not in ("exc", "bue"): continue
            html += (f'<div class="mk"><div class="row"><div class="mid">{mk["mercado"]}</div><span class="tag {e["cls"]}">{e["cal"]}</span></div>'
                     f'{barra(mk["prob"], e["tasa"], 1, P["ok"] if mk["prob"] >= 0.6 else "#b45309")}'
                     f'<div class="row small"><span>modelo <span class="w">{mk["prob"]:.0%}</span> · justa <span class="w">{mo.cuota_justa(mk["prob"])}</span></span>'
                     f'<span>últ.{n}: <span class="w">{e["hl"]}/{e["nl"]}</span> {local[:10]} · <span class="w">{e["hv"]}/{e["nv"]}</span> {visitante[:10]}</span></div></div>')
        st.markdown(html + '<div class="small" style="padding-top:6px">barra = prob. modelo · marca blanca = % histórico</div></div>', unsafe_allow_html=True)
        ss.ctx_ia = (f"Vista: Armar. Liga {LIGA}. Partido {partido}. Métrica {NOM[met]}. λ local {lam_l:.2f}, λ visitante {lam_v:.2f}, λ total {lam_l + lam_v:.2f}; "
                     f"media liga local {ml['local']:.2f}, visita {ml['visitante']:.2f}, total {ml['total']:.2f}. Validación con últimos {n} partidos.\n"
                     "Mercados del grupo " + grp + ":\n" + "\n".join(
                         f"- {mk['mercado']}: prob modelo {mk['prob']:.0%}, cuota justa {mo.cuota_justa(mk['prob'])}, "
                         f"{local} cumplió {ev_['hl']}/{ev_['nl']}, {visitante} {ev_['hv']}/{ev_['nv']}, calificación {ev_['cal']}"
                         for mk in lst if mk["grupo"] == grp for ev_ in [evaluar(mk, hl, hv)]) +
                     ("\nBoleto actual: " + "; ".join(f"{l['mercado']} ({l['partido']}, {l['metrica']}, modelo {l['prob']:.0%}, cuota casa {l['cuota']})" for l in ss.parlay)
                      if ss.parlay else "\nBoleto vacío."))

        st.markdown('<div class="t">Agregar al boleto</div>', unsafe_allow_html=True)
        nombres = [x["mercado"] for x in lst if x["grupo"] == grp]
        sel = st.selectbox("Mercado", nombres, key=f"sel_{met}_{grp}", label_visibility="collapsed")
        mk = next(x for x in lst if x["mercado"] == sel); e = evaluar(mk, hl, hv)
        a, b = st.columns(2)
        cuota = a.number_input("Cuota casa", 1.01, 50.0, 1.90, 0.01, key=f"cuota_{met}_{grp}", label_visibility="collapsed")
        ev = mk["prob"] * cuota - 1
        b.markdown(f'<div style="padding-top:6px"><span class="tag {e["cls"]}">{e["cal"]}</span> &nbsp; EV <b class="{"up" if ev > 0 else "down"}">{ev:+.2f}</b>'
                   f'<br><span class="small">modelo {mk["prob"]:.0%} · justa {mo.cuota_justa(mk["prob"])}</span></div>', unsafe_allow_html=True)
        a, b = st.columns(2)
        if a.button("Agregar al boleto", width="stretch"):
            ss.parlay.append({"partido": partido, "metrica": NOM[met], "mercado": sel, "prob": mk["prob"], "cuota": cuota,
                              "cal": e["cal"], "cls": e["cls"]})
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
        e = evaluar(mk, hl, hv)

        st.markdown(f'<div class="card"><div class="row"><div><div class="t">{sel} · {NOM[met]}</div>'
                    f'<div class="big">{mk["prob"]:.0%} <span class="small">modelo</span></div><div class="small">cuota justa {mo.cuota_justa(mk["prob"])}</div></div>'
                    f'<div style="text-align:right"><span class="tag {e["cls"]}">{e["cal"]}</span><div class="big" style="margin-top:4px">{e["tasa"]:.0%}</div>'
                    f'<div class="small">histórico · {e["hl"] + e["hv"]} de {e["nl"] + e["nv"]}</div></div></div>'
                    f'{barra(mk["prob"], e["tasa"], 1, P["acc"])}'
                    f'<div class="small">λ {local} {lam_l:.2f} {delta(lam_l, ml["local"], 2)} · λ {visitante} {lam_v:.2f} {delta(lam_v, ml["visitante"], 2)} · λ total {lam_l + lam_v:.2f} {delta(lam_l + lam_v, ml["total"], 2)} (vs media liga)</div></div>',
                    unsafe_allow_html=True)

        def bloque(nombre, h, hits_, lado, color):
            col = mk["col_l"] if lado == "l" else mk["col_v"]
            ref_f, ref_c = (ml["local"], ml["visitante"]) if lado == "l" else (ml["visitante"], ml["local"])
            que = {"a_favor": "a favor", "en_contra": "en contra", "total": "total"}.get(col, sel)
            ref_chart = {"a_favor": ref_f, "en_contra": ref_c}.get(col, ml["total"])
            if col in ("a_favor", "en_contra", "total"):
                chart = chart_barras(h, col, mk["linea"], ref_chart, mk["over"], color)
                sub = f"{NOM[met].lower()} {que} por partido · verde = cumplió la pata"
            else:
                chart = chart_barras(h, "total", ml["total"], ml["total"], True, color)
                sub = f"{NOM[met].lower()} total por partido · verde = sobre media liga"
            return (f'<div class="card"><div class="row"><div class="mid">{nombre}</div>'
                    f'<div><span class="w">{hits_}/{len(h)}</span> <span class="small">cumplió</span></div></div>'
                    f'{chart}<div class="small">{sub} · antiguo → reciente · C casa / F fuera</div>'
                    f'<div style="margin-top:10px">{tabla_stats(h, mk["linea"], mk["over"], ref_f, ref_c, ml["total"])}</div></div>')

        st.markdown(bloque(local, hl, e["hl"], "l", P["acc"]) + bloque(visitante, hv, e["hv"], "v", "#8b5cf6"), unsafe_allow_html=True)
        def _st(h):
            return (f"a favor media {h.a_favor.mean():.1f} mediana {h.a_favor.median():.1f} desv {h.a_favor.std(ddof=0):.1f}; "
                    f"en contra media {h.en_contra.mean():.1f}; total media {h.total.mean():.1f} máx {h.total.max()} mín {h.total.min()}") if len(h) else "sin partidos"
        ss.ctx_ia = (f"Vista: Analizar. Liga {LIGA}. Partido {partido}. Métrica {NOM[met]}. Pata: {sel}. Prob modelo {mk['prob']:.0%}, cuota justa {mo.cuota_justa(mk['prob'])}, "
                     f"calificación {e['cal']}, cumplimiento histórico {e['tasa']:.0%} ({e['hl']}/{e['nl']} {local}, {e['hv']}/{e['nv']} {visitante}) "
                     f"en últimos {n} partidos, filtro {filtro}. λ {local} {lam_l:.2f}, λ {visitante} {lam_v:.2f}, media liga local {ml['local']:.2f} visita {ml['visitante']:.2f} total {ml['total']:.2f}.\n"
                     f"{local} últimos {len(hl)}: {_st(hl)}. Resultados (reciente→antiguo): " + ", ".join(f"{r_.condicion[0]} vs {r_.rival} {r_.marcador} ({int(r_.a_favor)}-{int(r_.en_contra)} {NOM[met].lower()})" for _, r_ in hl.iterrows()) +
                     f"\n{visitante} últimos {len(hv)}: {_st(hv)}. Resultados: " + ", ".join(f"{r_.condicion[0]} vs {r_.rival} {r_.marcador} ({int(r_.a_favor)}-{int(r_.en_contra)} {NOM[met].lower()})" for _, r_ in hv.iterrows()) +
                     ("\nBoleto actual: " + "; ".join(f"{l['mercado']} ({l['partido']}, modelo {l['prob']:.0%}, cuota {l['cuota']})" for l in ss.parlay) if ss.parlay else "\nBoleto vacío."))

        with st.expander("Partido a partido", expanded=True):
            st.markdown(lista_partidos(local, hl, mk, "l") + lista_partidos(visitante, hv, mk, "v"), unsafe_allow_html=True)
        with st.expander("Qué dice el modelo", expanded=False):
            if met in GOL and mk["grupo"] in ("Resultado", "Total"):
                st.markdown(f'<div class="card">{matriz_html(r["matriz"], local, visitante, mk["region"])}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="card">{distribucion_html(r["matriz"], mk, NOM[met].lower() + (" total" if mk["grupo"] == "Total" else " " + mk["grupo"]))}</div>',
                            unsafe_allow_html=True)

        a, b = st.columns(2)
        cuota = a.number_input("Cuota casa", 1.01, 50.0, 1.90, 0.01, key=f"cuota_an_{met}", label_visibility="collapsed")
        if b.button("Agregar al boleto", width="stretch", key="add_an"):
            ss.parlay.append({"partido": partido, "metrica": NOM[met], "mercado": sel, "prob": mk["prob"], "cuota": cuota,
                              "cal": e["cal"], "cls": e["cls"]})
            registrar_uso("pata", f"{partido} | {sel} @ {cuota}")
            ss.grp = grp
            ir_a("Armar")

st.markdown(f"""<style>
  div[data-testid="stPopover"] {{position:fixed; bottom:22px; right:18px; z-index:1000;}}
  div[data-testid="stPopover"] > button {{border-radius:999px; padding:10px 18px; font-weight:700; background:{P['acc']}; color:#fff; border:none; box-shadow:0 6px 20px rgba(0,0,0,.35);}}
  div[data-testid="stPopoverBody"] {{width:min(92vw, 420px); max-height:70vh; overflow:auto;}}
  .msg {{padding:8px 11px; border-radius:12px; margin:5px 0; font-size:0.84rem; line-height:1.35;}}
  .msg.u {{background:{P['acc']}; color:#fff; margin-left:18%;}} .msg.a {{background:{P['card2']}; color:{P['txt']}; margin-right:8%;}}
</style>""", unsafe_allow_html=True)
with st.popover("Analista IA"):
    if not ss.chat:
        st.markdown(f'<div class="small">Pregúntame sobre lo que ves en pantalla: "¿qué opinas de esta pata?", "¿por qué el over sale Regular?", "debate mi parlay".</div>', unsafe_allow_html=True)
    for m in ss.chat[-8:]:
        st.markdown(f'<div class="msg {"u" if m["rol"] == "user" else "a"}">{m["txt"]}</div>', unsafe_allow_html=True)
    preg = st.text_input("Pregunta", key=f"ia_q{len(ss.chat)}", placeholder="Escribe tu pregunta…", label_visibility="collapsed")
    a, b = st.columns([3, 1])
    if a.button("Enviar", width="stretch", key="ia_send") and preg.strip():
        ss.chat.append({"rol": "user", "txt": preg.strip()})
        ss.chat.append({"rol": "assistant", "txt": preguntar_ia(preg.strip())})
        registrar_uso("ia", preg.strip()[:80])
        st.rerun()
    if b.button("Limpiar", width="stretch", key="ia_clear"):
        ss.chat = []; st.rerun()

st.caption(f"{LIGA}: {len(df)} partidos · último {df['fecha'].max():%d/%m/%Y} · football-data.co.uk · "
           "Calificación = 60% prob. modelo + 40% cumplimiento histórico · EV = prob × cuota − 1 · "
           "Kelly = ((cuota−1)·p − (1−p)) / (cuota−1)")

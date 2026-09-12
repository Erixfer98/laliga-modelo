"""
app.py — Parlay La Liga. Dos modos:
  🎫 Armar   : productivo. Partido -> metrica -> mercados con prob, cuota justa, calificacion -> boleto.
  📊 Analizar: descriptivo. Un mercado concreto, N partidos a eleccion, aciertos partido a partido,
               comparacion vs liga, casa/fuera y distribucion del modelo con la zona del mercado marcada.
Local: streamlit run app.py
"""

import math

import numpy as np
import pandas as pd
import streamlit as st

import modelo as mo

st.set_page_config(page_title="Parlay La Liga", page_icon="⚽", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
  .block-container {padding: 0.5rem 0.8rem 4rem 0.8rem; max-width: 620px;}
  .card {background:#1c1f26; border-radius:14px; padding:12px 14px; margin:8px 0; color:#e6e6e6;}
  .t {font-size:0.72rem; color:#9aa0a6; text-transform:uppercase; letter-spacing:.05em;}
  .row {display:flex; justify-content:space-between; align-items:center; gap:8px;}
  .big {font-size:1.7rem; font-weight:700; line-height:1.1;}
  .mid {font-size:1rem; font-weight:600;}
  .small {font-size:0.78rem; color:#9aa0a6;}
  .bar {height:8px; border-radius:4px; background:#2c313a; position:relative; margin:5px 0 2px 0;}
  .bar > div {height:8px; border-radius:4px;}
  .bar .mark {position:absolute; top:-3px; width:2px; height:14px; background:#fff; opacity:.85;}
  .pill {display:inline-block; min-width:40px; text-align:center; padding:4px 5px; border-radius:8px;
         font-weight:700; font-size:0.8rem; margin:2px 1px; color:#fff; line-height:1.15;}
  .hit {background:#2e9e5b;} .miss {background:#3a3f4a; color:#9aa0a6;}
  .mk {border-top:1px solid #2c313a; padding:9px 0;}
  .tag {display:inline-block; padding:2px 8px; border-radius:6px; font-size:0.72rem; font-weight:700; white-space:nowrap;}
  .exc {background:#166534; color:#dcfce7;} .bue {background:#2e9e5b; color:#fff;} .reg {background:#b45309; color:#fff;}
  .mal {background:#991b1b; color:#fee2e2;} .pes {background:#450a0a; color:#fca5a5;}
  .up {color:#4ade80;} .down {color:#f87171;}
  .sticky {position:sticky; top:0; z-index:99; background:#0f1115; padding:6px 0;}
  table.mx {border-collapse:separate; border-spacing:3px; width:100%; font-size:0.78rem;}
  table.mx td {text-align:center; padding:6px 0; border-radius:6px; color:#e6e6e6;}
  table.mx th {font-size:0.72rem; color:#9aa0a6; font-weight:500; padding:2px;}
  .dist {display:flex; align-items:flex-end; gap:3px; height:90px; margin-top:8px;}
  .dist > div {flex:1; border-radius:4px 4px 0 0; position:relative;}
  .dist > div span {position:absolute; bottom:-18px; left:0; right:0; text-align:center; font-size:0.68rem; color:#9aa0a6;}
</style>""", unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def datos():
    return mo.cargar()


df = datos()
lista = mo.equipos(df)
st.session_state.setdefault("parlay", [])
GOL = ("goles", "goles_1t", "goles_2t")


# ================================================================== mercados
def historial(equipo, met, n, condicion=None):
    """Ultimos n partidos con columnas booleanas para evaluar cualquier mercado."""
    h = mo.ultimos_n(df, equipo, met, 60)
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


def cumple(h, mk):
    """Serie booleana: en que partidos del historial se habria cumplido el mercado (mk['lado']: 'l' o 'v')."""
    col = mk["col_l"] if mk["lado"] == "l" else mk["col_v"]
    return (h[col] > mk["linea"]) if mk["over"] else (h[col] < mk["linea"])


def calificar(p, tasa):
    s = 0.6 * p + 0.4 * tasa
    for lim, txt, cls in ((0.78, "Excelente", "exc"), (0.68, "Buena", "bue"), (0.56, "Regular", "reg"), (0.45, "Mala", "mal")):
        if s >= lim:
            return txt, cls
    return "Pésima", "pes"


def lineas_total(lam_tot, met):
    if met == "goles": return [0.5, 1.5, 2.5, 3.5, 4.5]
    if met in GOL: return [0.5, 1.5, 2.5]
    if met == "rojas": return [0.5, 1.5]
    c = round(lam_tot); return [x for x in (c - 2.5, c - 1.5, c - 0.5, c + 0.5, c + 1.5, c + 2.5) if x > 0]


def lineas_equipo(lam, met):
    if met == "goles": return [0.5, 1.5, 2.5]
    if met in GOL: return [0.5, 1.5]
    if met == "rojas": return [0.5]
    c = round(lam); return [x for x in (c - 1.5, c - 0.5, c + 0.5, c + 1.5) if x > 0]


def mercados(r, met, local, visitante):
    """Cada mercado: nombre, grupo, prob, y como evaluarlo en el historial de cada equipo (col_l/col_v, linea, over)."""
    m, lam_l, lam_v = r["matriz"], r["lambda_local"], r["lambda_visitante"]
    k = m.shape[0]; tot = np.add.outer(np.arange(k), np.arange(k))
    out = []

    def add(nombre, grupo, p, col_l, col_v, linea, over, region):
        out.append({"mercado": nombre, "grupo": grupo, "prob": float(p), "col_l": col_l, "col_v": col_v,
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
    for ln in lineas_total(lam_l + lam_v, met):
        po = m[tot > ln].sum()
        add(f"Total Over {ln}", "Total", po, "total", "total", ln, True, lambda x, y, ln=ln: x + y > ln)
        add(f"Total Under {ln}", "Total", 1 - po, "total", "total", ln, False, lambda x, y, ln=ln: x + y < ln)
    for ln in lineas_equipo(lam_l, met):
        po = mo.prob_over(lam_l, ln)
        add(f"{local} Over {ln}", local, po, "a_favor", "en_contra", ln, True, lambda x, y, ln=ln: x > ln)
        add(f"{local} Under {ln}", local, 1 - po, "a_favor", "en_contra", ln, False, lambda x, y, ln=ln: x < ln)
    for ln in lineas_equipo(lam_v, met):
        po = mo.prob_over(lam_v, ln)
        add(f"{visitante} Over {ln}", visitante, po, "en_contra", "a_favor", ln, True, lambda x, y, ln=ln: y > ln)
        add(f"{visitante} Under {ln}", visitante, 1 - po, "en_contra", "a_favor", ln, False, lambda x, y, ln=ln: y < ln)
    return out


def evaluar(mk, hl, hv):
    cl, cv = cumple(hl, {**mk, "lado": "l"}), cumple(hv, {**mk, "lado": "v"})
    n = len(hl) + len(hv)
    tasa = (cl.sum() + cv.sum()) / n if n else 0
    txt, cls = calificar(mk["prob"], tasa)
    return {"hl": int(cl.sum()), "nl": len(hl), "hv": int(cv.sum()), "nv": len(hv), "tasa": tasa, "cal": txt, "cls": cls,
            "serie_l": cl, "serie_v": cv}


# ================================================================== piezas visuales
def barra(valor, marca, maximo, color="#2b6cb0"):
    pct = min(valor / maximo, 1) * 100 if maximo else 0
    mk = min(marca / maximo, 1) * 100 if maximo else 0
    return f'<div class="bar"><div style="width:{pct:.0f}%;background:{color}"></div><div class="mark" style="left:{mk:.0f}%"></div></div>'


def delta(v, ref, dec=1):
    return f'<span class="{"up" if v - ref >= 0 else "down"}">{v - ref:+.{dec}f}</span>'


def pills(h, serie):
    """Un chip por partido (antiguo -> reciente): verde si el mercado se cumplio."""
    s = ""
    for (_, g), ok in zip(h.iloc[::-1].iterrows(), serie.iloc[::-1]):
        s += (f'<span class="pill {"hit" if ok else "miss"}" title="{g.rival} {g.fecha}">{g.a_favor}-{g.en_contra}'
              f'<br><span style="font-size:.6rem;opacity:.75">{"C" if g.condicion == "Casa" else "F"}</span></span>')
    return s


def matriz_html(m, local, visitante, region, k=6):
    """Matriz de marcadores. Opacidad = probabilidad; verde = marcadores que hacen ganar el mercado."""
    mx = m[:k, :k].max()
    h = f'<table class="mx"><tr><th></th>' + "".join(f"<th>{y}</th>" for y in range(k)) + "</tr>"
    for x in range(k):
        h += f"<tr><th>{x}</th>"
        for y in range(k):
            p = m[x, y]; a = 0.15 + 0.85 * (p / mx)
            col = f"rgba(46,158,91,{a:.2f})" if region(x, y) else f"rgba(90,98,112,{a * 0.7:.2f})"
            h += f'<td style="background:{col}">{p * 100:.0f}</td>'
        h += "</tr>"
    h += "</table>"
    h += f'<div class="small" style="margin-top:4px">filas = {local}, columnas = {visitante}, cifra = % del modelo · verde = gana la pata</div>'
    return h


def distribucion_html(m, mk, lam_tot):
    """Distribucion del total (o de un equipo) con la zona del mercado en verde."""
    k = m.shape[0]
    if mk["grupo"] == "Total":
        tot = np.add.outer(np.arange(k), np.arange(k))
        dist = np.array([m[tot == s].sum() for s in range(k * 2 - 1)])
        cond = (lambda s: s > mk["linea"]) if mk["over"] else (lambda s: s < mk["linea"])
        etiqueta = "total"
    else:
        eje = 1 if mk["col_l"] == "a_favor" else 0    # equipo local -> sumar por filas
        dist = m.sum(axis=eje)
        cond = (lambda s: s > mk["linea"]) if mk["over"] else (lambda s: s < mk["linea"])
        etiqueta = mk["grupo"]
    lo, hi = 0, len(dist)
    while hi > 1 and dist[hi - 1] < 0.005: hi -= 1
    hi = max(hi, int(mk["linea"]) + 2)
    mx = dist[lo:hi].max()
    h = '<div class="dist">'
    for s in range(lo, hi):
        col = "#2e9e5b" if cond(s) else "#3a3f4a"
        h += f'<div style="height:{max(dist[s] / mx * 100, 2):.0f}%;background:{col}"><span>{s}</span></div>'
    return h + f'</div><div class="small" style="margin-top:22px">{etiqueta} esperado según el modelo · verde = gana la pata (línea {mk["linea"]})</div>'


# ================================================================== cabecera comun
st.markdown("### ⚽ Parlay La Liga")
modo = st.segmented_control("Modo", ["🎫 Armar", "📊 Analizar"], default="🎫 Armar", label_visibility="collapsed") or "🎫 Armar"
c1, c2 = st.columns(2)
local = c1.selectbox("Local", lista, index=lista.index("Real Madrid") if "Real Madrid" in lista else 0)
visitante = c2.selectbox("Visitante", [e for e in lista if e != local])
partido = f"{local} vs {visitante}"
met = st.pills("Métrica", list(mo.METRICAS), format_func=lambda x: mo.NOMBRES[x], default="goles",
               label_visibility="collapsed") or "goles"
r = mo.analizar(df, local, visitante, met)
lam_l, lam_v = r["lambda_local"], r["lambda_visitante"]
ml = mo.medias_liga(df, met)
lst = mercados(r, met, local, visitante)
grupos = list(dict.fromkeys(x["grupo"] for x in lst))

# ================================================================== MODO ARMAR
if modo == "🎫 Armar":
    n = st.session_state.get("n_armar", 5)
    legs = st.session_state.parlay
    if legs:
        prob = float(np.prod([l["prob"] for l in legs])); cuota = float(np.prod([l["cuota"] for l in legs])); ev = prob * cuota - 1
        st.markdown(f'<div class="sticky"><div class="card" style="margin:0"><div class="row">'
                    f'<div><div class="t">Boleto · {len(legs)} pata{"s" if len(legs) > 1 else ""}</div><div class="mid">cuota {cuota:.2f} · justa {mo.cuota_justa(prob)}</div></div>'
                    f'<div style="text-align:right"><div class="t">modelo {prob:.0%}</div><div class="big {"up" if ev > 0 else "down"}">EV {ev:+.2f}</div></div>'
                    f'</div></div></div>', unsafe_allow_html=True)
        with st.expander("Ver patas del boleto"):
            for i, l in enumerate(legs):
                a, b = st.columns([6, 1])
                a.markdown(f'<div class="row" style="padding:4px 0"><div><div class="mid">{l["mercado"]}</div>'
                           f'<div class="small">{l["partido"]} · {l["metrica"]} · modelo {l["prob"]:.0%} · justa {mo.cuota_justa(l["prob"])} · casa {l["cuota"]:.2f}</div></div>'
                           f'<span class="tag {l["cls"]}">{l["cal"]}</span></div>', unsafe_allow_html=True)
                if b.button("✕", key=f"del{i}"):
                    legs.pop(i); st.rerun()
            if len({l["partido"] for l in legs}) < len(legs):
                st.caption("⚠️ Patas del mismo partido no son independientes; la prob. combinada real difiere.")
            if st.button("Vaciar boleto"):
                st.session_state.parlay = []; st.rerun()

    st.markdown(f'<div class="card"><div class="row"><div><div class="t">{mo.NOMBRES[met]} · esperado</div>'
                f'<div class="mid">{local} <b>{lam_l:.2f}</b> · {visitante} <b>{lam_v:.2f}</b> · total <b>{lam_l + lam_v:.2f}</b></div>'
                f'<div class="small">liga: local {ml["local"]:.1f} · visita {ml["visitante"]:.1f} · total {ml["total"]:.1f}</div></div></div></div>',
                unsafe_allow_html=True)

    a, b = st.columns([3, 2])
    grp = a.pills("Grupo", grupos, default=grupos[0], label_visibility="collapsed") or grupos[0]
    st.session_state.n_armar = b.selectbox("Validar con últimos", [3, 5, 8, 10, 15], index=[3, 5, 8, 10, 15].index(n),
                                           format_func=lambda x: f"últ. {x}", label_visibility="collapsed")
    n = st.session_state.n_armar
    hl, hv = historial(local, met, n), historial(visitante, met, n)
    solo = st.toggle("Solo Buena o mejor", value=False)

    html = '<div class="card">'
    for mk in lst:
        if mk["grupo"] != grp: continue
        e = evaluar(mk, hl, hv)
        if solo and e["cls"] not in ("exc", "bue"): continue
        html += (f'<div class="mk"><div class="row"><div class="mid">{mk["mercado"]}</div><span class="tag {e["cls"]}">{e["cal"]}</span></div>'
                 f'{barra(mk["prob"], 0.5, 1, "#2e9e5b" if mk["prob"] >= 0.6 else "#b45309")}'
                 f'<div class="row small"><span>modelo <b style="color:#fff">{mk["prob"]:.0%}</b> · justa <b style="color:#fff">{mo.cuota_justa(mk["prob"])}</b></span>'
                 f'<span>últ.{n}: <b style="color:#fff">{e["hl"]}/{e["nl"]}</b> {local[:10]} · <b style="color:#fff">{e["hv"]}/{e["nv"]}</b> {visitante[:10]}</span></div></div>')
    st.markdown(html + "</div>", unsafe_allow_html=True)

    st.markdown("**Agregar al boleto**")
    nombres = [x["mercado"] for x in lst if x["grupo"] == grp]
    sel = st.selectbox("Mercado", nombres, key=f"sel_{met}_{grp}", label_visibility="collapsed")
    a, b = st.columns(2)
    cuota = a.number_input("Cuota casa", 1.01, 50.0, 1.90, 0.01, key=f"cuota_{met}_{grp}", label_visibility="collapsed")
    mk = next(x for x in lst if x["mercado"] == sel); e = evaluar(mk, hl, hv); ev = mk["prob"] * cuota - 1
    b.markdown(f'<div style="padding-top:6px"><span class="tag {e["cls"]}">{e["cal"]}</span> &nbsp; EV <b class="{"up" if ev > 0 else "down"}">{ev:+.2f}</b>'
               f'<br><span class="small">modelo {mk["prob"]:.0%} · justa {mo.cuota_justa(mk["prob"])}</span></div>', unsafe_allow_html=True)
    if st.button("➕ Agregar al boleto", width="stretch"):
        st.session_state.parlay.append({"partido": partido, "metrica": mo.NOMBRES[met], "mercado": sel,
                                        "prob": mk["prob"], "cuota": cuota, "cal": e["cal"], "cls": e["cls"]})
        st.rerun()

# ================================================================== MODO ANALIZAR
else:
    st.markdown('<div class="t" style="margin-top:6px">Mercado a analizar</div>', unsafe_allow_html=True)
    a, b = st.columns([3, 2])
    grp = a.pills("Grupo", grupos, default=grupos[0], label_visibility="collapsed", key="grp_an") or grupos[0]
    nombres = [x["mercado"] for x in lst if x["grupo"] == grp]
    sel = st.selectbox("Mercado", nombres, key=f"an_{met}_{grp}", label_visibility="collapsed")
    mk = next(x for x in lst if x["mercado"] == sel)
    n = st.slider("Últimos N partidos", 3, 30, 10)
    filtro = st.pills("Condición", ["Todos", "Como jugarán (casa/fuera)"], default="Todos", label_visibility="collapsed") or "Todos"
    cond_l, cond_v = ("Casa", "Fuera") if filtro != "Todos" else (None, None)
    hl, hv = historial(local, met, n, cond_l), historial(visitante, met, n, cond_v)
    e = evaluar(mk, hl, hv)

    # --- veredicto
    st.markdown(f'<div class="card"><div class="row"><div><div class="t">{sel}</div>'
                f'<div class="big">{mk["prob"]:.0%} <span class="small">modelo</span></div><div class="small">cuota justa {mo.cuota_justa(mk["prob"])}</div></div>'
                f'<div style="text-align:right"><span class="tag {e["cls"]}">{e["cal"]}</span><div class="big" style="margin-top:4px">{e["tasa"]:.0%}</div>'
                f'<div class="small">se cumplió en {e["hl"] + e["hv"]} de {e["nl"] + e["nv"]} partidos</div></div></div>'
                f'{barra(mk["prob"], e["tasa"], 1, "#2b6cb0")}<div class="small">barra = modelo · marca blanca = histórico</div></div>',
                unsafe_allow_html=True)

    # --- partido a partido
    def bloque(nombre, h, serie, hits_, color):
        if h.empty:
            return f'<div class="card"><div class="mid">{nombre}</div><div class="small">sin partidos con ese filtro</div></div>'
        fa, co = h.a_favor.mean(), h.en_contra.mean()
        ref_f, ref_c = (ml["local"], ml["visitante"]) if color == "l" else (ml["visitante"], ml["local"])
        col = "#2b6cb0" if color == "l" else "#7c3aed"
        maxi = max(ml["total"], h.total.max(), 1)
        racha = 0
        for ok in serie:  # mas reciente primero
            if ok: racha += 1
            else: break
        return (f'<div class="card"><div class="row"><div class="mid">{nombre}</div>'
                f'<div><b>{hits_}/{len(h)}</b> <span class="small">cumplió · racha actual {racha}</span></div></div>'
                f'<div style="margin:6px 0">{pills(h, serie)}</div>'
                f'<div class="small">A favor <b style="color:#fff">{fa:.1f}</b> {delta(fa, ref_f)} vs liga {ref_f:.1f}</div>{barra(fa, ref_f, maxi, col)}'
                f'<div class="small">En contra <b style="color:#fff">{co:.1f}</b> {delta(co, ref_c)} vs liga {ref_c:.1f}</div>{barra(co, ref_c, maxi, "#6b7280")}'
                f'<div class="small" style="margin-top:6px">antiguo → reciente · C casa / F fuera · cifra = {mo.NOMBRES[met].lower()} a favor-en contra</div></div>')

    st.markdown(bloque(local, hl, e["serie_l"], e["hl"], "l") + bloque(visitante, hv, e["serie_v"], e["hv"], "v"), unsafe_allow_html=True)

    # --- modelo: matriz (goles) o distribucion
    st.markdown('<div class="t" style="margin-top:6px">Qué dice el modelo</div>', unsafe_allow_html=True)
    if met in GOL and mk["grupo"] in ("Resultado", "Total"):
        st.markdown(f'<div class="card">{matriz_html(r["matriz"], local, visitante, mk["region"])}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="card">{distribucion_html(r["matriz"], mk, lam_l + lam_v)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="card"><div class="row"><div><div class="t">λ {local}</div><div class="mid">{lam_l:.2f} {delta(lam_l, ml["local"], 2)}</div></div>'
                f'<div><div class="t">λ total</div><div class="mid">{lam_l + lam_v:.2f} {delta(lam_l + lam_v, ml["total"], 2)}</div></div>'
                f'<div><div class="t">λ {visitante}</div><div class="mid">{lam_v:.2f} {delta(lam_v, ml["visitante"], 2)}</div></div></div>'
                f'<div class="small">diferencia vs media de liga (local {ml["local"]:.2f} · total {ml["total"]:.2f} · visita {ml["visitante"]:.2f})</div></div>',
                unsafe_allow_html=True)
    with st.expander("Tabla de partidos"):
        cols = ["fecha", "condicion", "rival", "marcador", "a_favor", "en_contra", "total"]
        st.markdown(f"**{local}**"); st.dataframe(hl[cols], hide_index=True, width="stretch")
        st.markdown(f"**{visitante}**"); st.dataframe(hv[cols], hide_index=True, width="stretch")

st.caption(f"{len(df)} partidos · último {df['fecha'].max():%d/%m/%Y} · football-data.co.uk · "
           "Calificación = 60% prob. modelo + 40% cumplimiento histórico · EV = prob × cuota − 1")

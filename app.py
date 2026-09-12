"""
app.py — Parlay La Liga.
  🎫 Armar   : mercados con linea configurable, prob, cuota justa, calificacion -> boleto.
  📊 Analizar: estadisticas descriptivas (media, mediana, desviacion, min, max, % cumple) de la pata elegida,
               con N, casa/fuera y linea configurables, barras partido a partido y distribucion del modelo.
Local: streamlit run app.py
"""

import numpy as np
import pandas as pd
import streamlit as st

import modelo as mo

st.set_page_config(page_title="Parlay La Liga", page_icon="⚽", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
  header[data-testid="stHeader"] {display:none;}
  .stApp {background:#0f1115; color:#e6e6e6;}
  .block-container {padding: 0.8rem 0.8rem 4rem 0.8rem; max-width: 620px;}
  h3 {color:#e6e6e6 !important; margin:0 0 4px 0 !important; padding:0 !important;}
  label, .stMarkdown p, .stCaption {color:#c9cdd3 !important;}
  .card {background:#1c1f26; border-radius:14px; padding:12px 14px; margin:8px 0; color:#e6e6e6;}
  .t {font-size:0.72rem; color:#9aa0a6; text-transform:uppercase; letter-spacing:.05em;}
  .row {display:flex; justify-content:space-between; align-items:center; gap:8px;}
  .big {font-size:1.7rem; font-weight:700; line-height:1.1;}
  .mid {font-size:1rem; font-weight:600;}
  .small {font-size:0.78rem; color:#9aa0a6;}
  .w {color:#fff; font-weight:600;}
  .bar {height:8px; border-radius:4px; background:#2c313a; position:relative; margin:5px 0 2px 0;}
  .bar > div {height:8px; border-radius:4px;}
  .bar .mark {position:absolute; top:-3px; width:2px; height:14px; background:#fff; opacity:.85;}
  .mk {border-top:1px solid #2c313a; padding:9px 0;}
  .tag {display:inline-block; padding:2px 8px; border-radius:6px; font-size:0.72rem; font-weight:700; white-space:nowrap;}
  .exc {background:#166534; color:#dcfce7;} .bue {background:#2e9e5b; color:#fff;} .reg {background:#b45309; color:#fff;}
  .mal {background:#991b1b; color:#fee2e2;} .pes {background:#450a0a; color:#fca5a5;}
  .up {color:#4ade80;} .down {color:#f87171;}
  .sticky {position:sticky; top:0; z-index:99; background:#0f1115; padding:4px 0;}
  table.st {width:100%; border-collapse:collapse; font-size:0.82rem;}
  table.st th {text-align:right; font-weight:500; color:#9aa0a6; padding:5px 4px; border-bottom:1px solid #2c313a;}
  table.st th:first-child, table.st td:first-child {text-align:left; color:#9aa0a6;}
  table.st td {text-align:right; padding:5px 4px; border-bottom:1px solid #22262e;}
  table.st tr.liga td {color:#9aa0a6; font-style:italic;}
  table.mx {border-collapse:separate; border-spacing:3px; width:100%; font-size:0.78rem;}
  table.mx td {text-align:center; padding:6px 0; border-radius:6px; color:#e6e6e6;}
  table.mx th {font-size:0.72rem; color:#9aa0a6; font-weight:500; padding:2px;}
  .chart {position:relative; height:110px; margin:26px 0 22px 0;}
  .chart .bars {display:flex; align-items:flex-end; gap:3px; height:100%;}
  .chart .bars > div {flex:1; border-radius:4px 4px 0 0; position:relative; min-width:6px;}
  .chart .bars > div .v {position:absolute; top:-16px; left:0; right:0; text-align:center; font-size:0.66rem; color:#c9cdd3;}
  .chart .bars > div .x {position:absolute; bottom:-16px; left:0; right:0; text-align:center; font-size:0.62rem; color:#9aa0a6;}
  .chart .ln {position:absolute; left:0; right:0; border-top:2px dashed #fff; opacity:.8;}
  .chart .ln span {position:absolute; right:0; top:-14px; font-size:0.66rem; color:#fff;}
  .chart .lg {position:absolute; left:0; right:0; border-top:2px dotted #f59e0b; opacity:.9;}
  .chart .lg span {position:absolute; left:0; top:-14px; font-size:0.66rem; color:#f59e0b;}
</style>""", unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def datos():
    return mo.cargar()


df = datos()
lista = mo.equipos(df)
ss = st.session_state
ss.setdefault("parlay", [])
ss.setdefault("modo", "🎫 Armar")
ss.setdefault("gen", 0)   # cambia para reiniciar los widgets al saltar de modo
GOL = ("goles", "goles_1t", "goles_2t")
NOM = mo.NOMBRES


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
        c = color if ok else "#3a3f4a"
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


def matriz_html(m, local, visitante, region, k=6):
    mx = m[:k, :k].max()
    h = '<table class="mx"><tr><th></th>' + "".join(f"<th>{y}</th>" for y in range(k)) + "</tr>"
    for x in range(k):
        h += f"<tr><th>{x}</th>"
        for y in range(k):
            p = m[x, y]; a = 0.15 + 0.85 * (p / mx)
            col = f"rgba(46,158,91,{a:.2f})" if region(x, y) else f"rgba(90,98,112,{a * 0.7:.2f})"
            h += f'<td style="background:{col}">{p * 100:.0f}</td>'
        h += "</tr>"
    return h + f'</table><div class="small" style="margin-top:4px">filas = {local} · columnas = {visitante} · cifra = % modelo · verde = gana la pata</div>'


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
    hi = max(hi, int(mk["linea"]) + 2)
    mx = dist[:hi].max()
    bars = "".join(f'<div style="height:{max(dist[s] / mx * 100, 2):.0f}%;background:{"#2e9e5b" if cond(s) else "#3a3f4a"}">'
                   f'<span class="v">{dist[s]:.0%}</span><span class="x">{s}</span></div>' for s in range(hi))
    return f'<div class="chart"><div class="bars">{bars}</div></div><div class="small">{etiqueta} según el modelo · verde = gana la pata</div>'


# ================================================================== cabecera
st.markdown("### ⚽ Parlay La Liga")
modo = st.segmented_control("Modo", ["🎫 Armar", "📊 Analizar"], default=ss.modo, label_visibility="collapsed", key=f"modo_w{ss.gen}") or ss.modo
ss.modo = modo
c1, c2 = st.columns(2)
local = c1.selectbox("Local", lista, index=lista.index("Real Madrid") if "Real Madrid" in lista else 0)
visitante = c2.selectbox("Visitante", [e for e in lista if e != local])
partido = f"{local} vs {visitante}"
met = st.pills("Métrica", list(mo.METRICAS), format_func=lambda x: NOM[x], default=ss.get("met", "goles"),
               label_visibility="collapsed", key="met_w") or "goles"
ss.met = met
r = mo.analizar(df, local, visitante, met)
lam_l, lam_v = r["lambda_local"], r["lambda_visitante"]
ml = mo.medias_liga(df, met)

# configuracion de lineas (compartida entre modos, por metrica)
key_cfg = f"cfg_{met}_{local}_{visitante}"
if key_cfg not in ss:
    ss[key_cfg] = {"Total": [centro_defecto(lam_l + lam_v, met), 2 if met == "goles" else 1],
                   local: [centro_defecto(lam_l, met), 1], visitante: [centro_defecto(lam_v, met), 1]}
cfg = ss[key_cfg]
lst = mercados(r, met, local, visitante, cfg)
grupos = list(dict.fromkeys(x["grupo"] for x in lst))


def selector_lineas(grp, key):
    """Centro y rango de lineas para el grupo. Compacto: dos controles en una fila."""
    if grp == "Resultado":
        return
    a, b = st.columns([1, 1])
    centro = a.number_input(f"Línea {grp[:14]}", 0.5, 60.5, float(cfg[grp][0]), 1.0, key=f"c_{key}_{grp}")
    rango = b.selectbox("± líneas", [0, 1, 2, 3, 4], index=cfg[grp][1], key=f"r_{key}_{grp}")
    if [centro, rango] != cfg[grp]:
        cfg[grp] = [centro, rango]; st.rerun()


# ================================================================== MODO ARMAR
if modo == "🎫 Armar":
    legs = ss.parlay
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
                ss.parlay = []; st.rerun()

    st.markdown(f'<div class="card"><div class="t">{NOM[met]} · esperado del modelo</div>'
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
                 f'{barra(mk["prob"], e["tasa"], 1, "#2e9e5b" if mk["prob"] >= 0.6 else "#b45309")}'
                 f'<div class="row small"><span>modelo <span class="w">{mk["prob"]:.0%}</span> · justa <span class="w">{mo.cuota_justa(mk["prob"])}</span></span>'
                 f'<span>últ.{n}: <span class="w">{e["hl"]}/{e["nl"]}</span> {local[:10]} · <span class="w">{e["hv"]}/{e["nv"]}</span> {visitante[:10]}</span></div></div>')
    st.markdown(html + '<div class="small" style="padding-top:6px">barra = prob. modelo · marca blanca = % histórico</div></div>', unsafe_allow_html=True)

    st.markdown("**Agregar al boleto**")
    nombres = [x["mercado"] for x in lst if x["grupo"] == grp]
    sel = st.selectbox("Mercado", nombres, key=f"sel_{met}_{grp}", label_visibility="collapsed")
    mk = next(x for x in lst if x["mercado"] == sel); e = evaluar(mk, hl, hv)
    a, b = st.columns(2)
    cuota = a.number_input("Cuota casa", 1.01, 50.0, 1.90, 0.01, key=f"cuota_{met}_{grp}", label_visibility="collapsed")
    ev = mk["prob"] * cuota - 1
    b.markdown(f'<div style="padding-top:6px"><span class="tag {e["cls"]}">{e["cal"]}</span> &nbsp; EV <b class="{"up" if ev > 0 else "down"}">{ev:+.2f}</b>'
               f'<br><span class="small">modelo {mk["prob"]:.0%} · justa {mo.cuota_justa(mk["prob"])}</span></div>', unsafe_allow_html=True)
    a, b = st.columns(2)
    if a.button("➕ Agregar al boleto", width="stretch"):
        ss.parlay.append({"partido": partido, "metrica": NOM[met], "mercado": sel, "prob": mk["prob"], "cuota": cuota,
                          "cal": e["cal"], "cls": e["cls"]})
        st.rerun()
    if b.button("🔍 Analizar esta pata", width="stretch"):
        ss.modo, ss.an_mercado, ss.grp = "📊 Analizar", sel, grp; ss.gen += 1
        st.rerun()

# ================================================================== MODO ANALIZAR
else:
    # --- que analizar
    grp = st.pills("Grupo", grupos, default=ss.get("grp", grupos[0]) if ss.get("grp") in grupos else grupos[0],
                   label_visibility="collapsed", key=f"grp_an{ss.gen}") or grupos[0]
    ss.grp = grp
    selector_lineas(grp, "an")
    nombres = [x["mercado"] for x in lst if x["grupo"] == grp]
    idx = nombres.index(ss.an_mercado) if ss.get("an_mercado") in nombres else 0
    sel = st.selectbox("Pata", nombres, index=idx, key=f"an_{met}_{grp}{ss.gen}", label_visibility="collapsed")
    mk = next(x for x in lst if x["mercado"] == sel)

    # --- filtros
    a, b = st.columns([3, 2])
    n = a.slider("Últimos N partidos", 3, 30, 10)
    filtro = b.selectbox("Condición", ["Todos", "Como jugarán"], label_visibility="collapsed",
                         help="Como jugarán = solo partidos del local en casa y del visitante fuera")
    cond_l, cond_v = ("Casa", "Fuera") if filtro != "Todos" else (None, None)
    hl, hv = historial(local, met, n, cond_l), historial(visitante, met, n, cond_v)
    e = evaluar(mk, hl, hv)

    # --- veredicto (una tarjeta)
    st.markdown(f'<div class="card"><div class="row"><div><div class="t">{sel} · {NOM[met]}</div>'
                f'<div class="big">{mk["prob"]:.0%} <span class="small">modelo</span></div><div class="small">cuota justa {mo.cuota_justa(mk["prob"])}</div></div>'
                f'<div style="text-align:right"><span class="tag {e["cls"]}">{e["cal"]}</span><div class="big" style="margin-top:4px">{e["tasa"]:.0%}</div>'
                f'<div class="small">histórico · {e["hl"] + e["hv"]} de {e["nl"] + e["nv"]}</div></div></div>'
                f'{barra(mk["prob"], e["tasa"], 1, "#2b6cb0")}'
                f'<div class="small">λ {local} {lam_l:.2f} {delta(lam_l, ml["local"], 2)} · λ {visitante} {lam_v:.2f} {delta(lam_v, ml["visitante"], 2)} · λ total {lam_l + lam_v:.2f} {delta(lam_l + lam_v, ml["total"], 2)} (vs media liga)</div></div>',
                unsafe_allow_html=True)

    # --- por equipo: barras + stats
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

    st.markdown(bloque(local, hl, e["hl"], "l", "#2b6cb0") + bloque(visitante, hv, e["hv"], "v", "#7c3aed"), unsafe_allow_html=True)

    # --- modelo
    with st.expander("Qué dice el modelo", expanded=False):
        if met in GOL and mk["grupo"] in ("Resultado", "Total"):
            st.markdown(f'<div class="card">{matriz_html(r["matriz"], local, visitante, mk["region"])}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="card">{distribucion_html(r["matriz"], mk, NOM[met].lower() + (" total" if mk["grupo"] == "Total" else " " + mk["grupo"]))}</div>',
                        unsafe_allow_html=True)
    with st.expander("Tabla de partidos"):
        cols = ["fecha", "condicion", "rival", "marcador", "a_favor", "en_contra", "total"]
        st.markdown(f"**{local}**"); st.dataframe(hl[cols], hide_index=True, width="stretch")
        st.markdown(f"**{visitante}**"); st.dataframe(hv[cols], hide_index=True, width="stretch")

    a, b = st.columns(2)
    cuota = a.number_input("Cuota casa", 1.01, 50.0, 1.90, 0.01, key=f"cuota_an_{met}", label_visibility="collapsed")
    if b.button("➕ Agregar al boleto", width="stretch", key="add_an"):
        ss.parlay.append({"partido": partido, "metrica": NOM[met], "mercado": sel, "prob": mk["prob"], "cuota": cuota,
                          "cal": e["cal"], "cls": e["cls"]})
        ss.modo, ss.grp = "🎫 Armar", grp; ss.gen += 1; st.rerun()

st.caption(f"{len(df)} partidos · último {df['fecha'].max():%d/%m/%Y} · football-data.co.uk · "
           "Calificación = 60% prob. modelo + 40% cumplimiento histórico · EV = prob × cuota − 1")

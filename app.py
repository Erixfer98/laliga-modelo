"""
app.py — Armador de parlays La Liga con Poisson/Dixon-Coles + descriptivos.
Local: streamlit run app.py
"""

import numpy as np
import pandas as pd
import streamlit as st

import modelo as mo

st.set_page_config(page_title="Parlay La Liga", page_icon="⚽", layout="wide")
st.markdown("""
<style>
  .block-container {padding-top: 1.2rem;}
  div[data-testid="stMetric"] {background: #f5f6f8; border-radius: 10px; padding: 8px 12px;}
  div[data-testid="stMetricLabel"] p {font-size: 0.8rem; color: #555;}
  .leg {border-left: 4px solid #2b6cb0; padding: 4px 8px; margin: 4px 0; background: #f8fafc; font-size: 0.85rem;}
  .ok {color: #15803d; font-weight: 600;} .bad {color: #b91c1c; font-weight: 600;}
</style>""", unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def datos():
    return mo.cargar()


df = datos()
lista = mo.equipos(df)
if "parlay" not in st.session_state:
    st.session_state.parlay = []


# ================================================================== mercados por metrica
def lineas_total(lam_tot: float, metrica: str) -> list:
    if metrica in ("goles", "goles_1t", "goles_2t"):
        return [0.5, 1.5, 2.5, 3.5, 4.5] if metrica == "goles" else [0.5, 1.5, 2.5]
    if metrica == "rojas":
        return [0.5, 1.5]
    c = round(lam_tot)
    return [c - 2.5, c - 1.5, c - 0.5, c + 0.5, c + 1.5, c + 2.5]


def lineas_equipo(lam: float, metrica: str) -> list:
    if metrica in ("goles", "goles_1t", "goles_2t"):
        return [0.5, 1.5, 2.5] if metrica == "goles" else [0.5, 1.5]
    if metrica == "rojas":
        return [0.5]
    c = round(lam)
    return [c - 1.5, c - 0.5, c + 0.5, c + 1.5]


def aciertos(h: pd.DataFrame, col: str, linea: float, over: bool) -> str:
    if h.empty:
        return "—"
    n = (h[col] > linea).sum() if over else (h[col] < linea).sum()
    return f"{n}/{len(h)}"


def tabla_mercados(r: dict, metrica: str, local: str, visitante: str, hl: pd.DataFrame, hv: pd.DataFrame) -> pd.DataFrame:
    """Un renglon por mercado: probabilidad del modelo, cuota justa y aciertos en ultimos N de cada equipo."""
    m, lam_l, lam_v = r["matriz"], r["lambda_local"], r["lambda_visitante"]
    k = m.shape[0]
    tot = np.add.outer(np.arange(k), np.arange(k))
    filas = []

    def add(nombre, p, ac_l, ac_v):
        filas.append({"Mercado": nombre, "Prob. modelo": p, "Cuota justa": mo.cuota_justa(p),
                      f"Últ. {len(hl)} {local}": ac_l, f"Últ. {len(hv)} {visitante}": ac_v})

    if metrica in ("goles", "goles_1t", "goles_2t"):
        p1, px, p2 = np.tril(m, -1).sum(), np.trace(m), np.triu(m, 1).sum()
        gl = (hl["a_favor"] > hl["en_contra"]).sum(); el = (hl["a_favor"] == hl["en_contra"]).sum()
        gv = (hv["a_favor"] > hv["en_contra"]).sum(); ev = (hv["a_favor"] == hv["en_contra"]).sum()
        n_l, n_v = len(hl), len(hv)
        add(f"Gana {local}", p1, f"{gl}/{n_l} ganó", f"{n_v-gv-ev}/{n_v} perdió")
        add("Empate", px, f"{el}/{n_l}", f"{ev}/{n_v}")
        add(f"Gana {visitante}", p2, f"{n_l-gl-el}/{n_l} perdió", f"{gv}/{n_v} ganó")
        add(f"{local} o empate (1X)", p1 + px, f"{gl+el}/{n_l}", f"{n_v-gv}/{n_v}")
        add(f"{visitante} o empate (X2)", p2 + px, f"{n_l-gl}/{n_l}", f"{gv+ev}/{n_v}")
        btts = m[1:, 1:].sum()
        add("Ambos anotan: Sí", btts, aciertos(hl.assign(x=(hl.a_favor > 0) & (hl.en_contra > 0)), "x", 0.5, True),
            aciertos(hv.assign(x=(hv.a_favor > 0) & (hv.en_contra > 0)), "x", 0.5, True))
        add("Ambos anotan: No", 1 - btts, aciertos(hl.assign(x=(hl.a_favor > 0) & (hl.en_contra > 0)), "x", 0.5, False),
            aciertos(hv.assign(x=(hv.a_favor > 0) & (hv.en_contra > 0)), "x", 0.5, False))

    for ln in lineas_total(lam_l + lam_v, metrica):
        if ln <= 0:
            continue
        po = m[tot > ln].sum()
        add(f"Total Over {ln}", po, aciertos(hl, "total", ln, True), aciertos(hv, "total", ln, True))
        add(f"Total Under {ln}", 1 - po, aciertos(hl, "total", ln, False), aciertos(hv, "total", ln, False))
    for ln in lineas_equipo(lam_l, metrica):
        if ln <= 0:
            continue
        po = mo.prob_over(lam_l, ln)
        add(f"{local} Over {ln}", po, aciertos(hl, "a_favor", ln, True), aciertos(hv, "en_contra", ln, True))
        add(f"{local} Under {ln}", 1 - po, aciertos(hl, "a_favor", ln, False), aciertos(hv, "en_contra", ln, False))
    for ln in lineas_equipo(lam_v, metrica):
        if ln <= 0:
            continue
        po = mo.prob_over(lam_v, ln)
        add(f"{visitante} Over {ln}", po, aciertos(hl, "en_contra", ln, True), aciertos(hv, "a_favor", ln, True))
        add(f"{visitante} Under {ln}", 1 - po, aciertos(hl, "en_contra", ln, False), aciertos(hv, "a_favor", ln, False))
    return pd.DataFrame(filas)


def color_prob(v):
    return f"background-color: rgba(43,108,176,{0.08 + 0.5 * v});" if isinstance(v, float) else ""


# ================================================================== sidebar: partido + parlay
with st.sidebar:
    st.header("Partido")
    local = st.selectbox("Local", lista, index=lista.index("Real Madrid") if "Real Madrid" in lista else 0)
    visitante = st.selectbox("Visitante", [e for e in lista if e != local])
    n_ult = st.slider("Últimos N partidos", 5, 20, 10)
    mo.RHO = st.number_input("ρ Dixon-Coles (goles)", value=-0.05, step=0.01, format="%.2f")

    st.divider()
    st.header("🎫 Tu parlay")
    if not st.session_state.parlay:
        st.caption("Vacío. Agrega mercados desde cada pestaña.")
    else:
        prob, cuota = 1.0, 1.0
        for i, leg in enumerate(st.session_state.parlay):
            prob *= leg["prob"]; cuota *= leg["cuota"]
            c1, c2 = st.columns([5, 1])
            c1.markdown(f'<div class="leg"><b>{leg["mercado"]}</b><br>{leg["partido"]} · {leg["metrica"]}<br>'
                        f'modelo {leg["prob"]:.0%} · justa {mo.cuota_justa(leg["prob"])} · casa {leg["cuota"]:.2f}</div>',
                        unsafe_allow_html=True)
            if c2.button("✕", key=f"del{i}"):
                st.session_state.parlay.pop(i); st.rerun()
        ev = prob * cuota - 1
        a, b = st.columns(2)
        a.metric("Prob. modelo", f"{prob:.1%}")
        b.metric("Cuota justa", f"{mo.cuota_justa(prob)}")
        a.metric("Cuota casa", f"{cuota:.2f}")
        b.metric("EV por Q1", f"{ev:+.2f}", delta="valor" if ev > 0 else "sin valor", delta_color="normal" if ev > 0 else "inverse")
        if len({l["partido"] for l in st.session_state.parlay}) < len(st.session_state.parlay):
            st.caption("⚠️ Hay patas del mismo partido: no son independientes, la prob. real es distinta a la multiplicada.")
        if st.button("Vaciar parlay"):
            st.session_state.parlay = []; st.rerun()

# ================================================================== encabezado + resumen
partido = f"{local} vs {visitante}"
st.title(partido)
st.caption(f"{len(df)} partidos · último cargado {df['fecha'].max():%d/%m/%Y} · λ = esperado del modelo · "
           f"media liga = promedio de todos los partidos · últ. {n_ult} = promedio reciente del equipo")

resultados, hist_l, hist_v, medias = {}, {}, {}, {}
resumen = []
for met in mo.METRICAS:
    r = mo.analizar(df, local, visitante, met)
    hl, hv = mo.ultimos_n(df, local, met, n_ult), mo.ultimos_n(df, visitante, met, n_ult)
    ml = mo.medias_liga(df, met)
    resultados[met], hist_l[met], hist_v[met], medias[met] = r, hl, hv, ml
    resumen.append({"Métrica": mo.NOMBRES[met],
                    f"λ {local}": r["lambda_local"], f"λ {visitante}": r["lambda_visitante"],
                    "λ total": r["lambda_local"] + r["lambda_visitante"],
                    "Media liga (total)": ml["total"],
                    f"Últ.{n_ult} {local} (total)": hl["total"].mean() if len(hl) else np.nan,
                    f"Últ.{n_ult} {visitante} (total)": hv["total"].mean() if len(hv) else np.nan})

st.subheader("Vista rápida: esperado vs liga vs racha")
st.dataframe(pd.DataFrame(resumen).set_index("Métrica").style.format("{:.2f}"), width="stretch")

# ================================================================== detalle por metrica
tabs = st.tabs([mo.NOMBRES[m] for m in mo.METRICAS])
for tab, met in zip(tabs, mo.METRICAS):
    r, hl, hv, ml = resultados[met], hist_l[met], hist_v[met], medias[met]
    lam_l, lam_v = r["lambda_local"], r["lambda_visitante"]
    with tab:
        # --- cards
        c = st.columns(6)
        c[0].metric(f"λ {local}", f"{lam_l:.2f}", f"{lam_l - ml['local']:+.2f} vs media local liga")
        c[1].metric(f"λ {visitante}", f"{lam_v:.2f}", f"{lam_v - ml['visitante']:+.2f} vs media visita liga")
        c[2].metric("λ total", f"{lam_l + lam_v:.2f}", f"{lam_l + lam_v - ml['total']:+.2f} vs media liga")
        c[3].metric(f"{local} últ.{len(hl)}: a favor / contra",
                    f"{hl.a_favor.mean():.1f} / {hl.en_contra.mean():.1f}" if len(hl) else "—")
        c[4].metric(f"{visitante} últ.{len(hv)}: a favor / contra",
                    f"{hv.a_favor.mean():.1f} / {hv.en_contra.mean():.1f}" if len(hv) else "—")
        c[5].metric("Media liga: local / visita / total", f"{ml['local']:.1f} / {ml['visitante']:.1f} / {ml['total']:.1f}")

        izq, der = st.columns([3, 2])
        # --- mercados
        with izq:
            st.markdown("#### Mercados")
            tm = tabla_mercados(r, met, local, visitante, hl, hv)
            st.dataframe(tm.style.format({"Prob. modelo": "{:.1%}", "Cuota justa": "{:.2f}"})
                         .map(color_prob, subset=["Prob. modelo"]), hide_index=True, width="stretch", height=380)

            st.markdown("**Agregar al parlay**")
            f1, f2, f3 = st.columns([3, 1, 1])
            sel = f1.selectbox("Mercado", tm["Mercado"], key=f"sel_{met}", label_visibility="collapsed")
            cuota = f2.number_input("Cuota casa", 1.01, 50.0, 1.90, 0.01, key=f"cuota_{met}", label_visibility="collapsed")
            p = float(tm.loc[tm["Mercado"] == sel, "Prob. modelo"].iloc[0])
            ev = p * cuota - 1
            f3.markdown(f'<span class="{"ok" if ev > 0 else "bad"}">EV {ev:+.2f}</span><br>'
                        f'<small>modelo {p:.0%} · justa {mo.cuota_justa(p)}</small>', unsafe_allow_html=True)
            if st.button("➕ Agregar", key=f"add_{met}"):
                st.session_state.parlay.append({"partido": partido, "metrica": mo.NOMBRES[met],
                                                "mercado": sel, "prob": p, "cuota": cuota})
                st.rerun()

        # --- historico
        with der:
            st.markdown(f"#### Últimos {n_ult} partidos")
            fmt = {"a_favor": "{:.0f}", "en_contra": "{:.0f}", "total": "{:.0f}"}
            st.markdown(f"**{local}** — media liga total {ml['total']:.1f}")
            st.dataframe(hl.style.format(fmt).background_gradient(subset=["total"], cmap="Blues"),
                         hide_index=True, width="stretch", height=200)
            st.markdown(f"**{visitante}**")
            st.dataframe(hv.style.format(fmt).background_gradient(subset=["total"], cmap="Blues"),
                         hide_index=True, width="stretch", height=200)

        with st.expander("Matriz de resultados del modelo"):
            k = min(r["matriz"].shape[0], 8)
            mm = pd.DataFrame(r["matriz"][:k, :k] * 100)
            mm.index.name, mm.columns.name = local, visitante
            st.dataframe(mm.style.background_gradient(cmap="Blues").format("{:.1f}%"), width="stretch")

st.caption("Fuente: football-data.co.uk, se actualiza cada lunes. Modelo: Poisson por equipo con peso por recencia; "
           "Dixon-Coles en goles y goles 1T. EV = prob. modelo × cuota − 1; positivo = el modelo ve valor.")

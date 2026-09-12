"""
app.py — Streamlit. Elige local y visitante y muestra el Poisson/Dixon-Coles de las 9 metricas.
Local:  streamlit run app.py
"""

import numpy as np
import pandas as pd
import streamlit as st

import modelo as mo

st.set_page_config(page_title="Poisson La Liga", layout="wide")


@st.cache_data(ttl=3600)
def datos():
    return mo.cargar()


df = datos()
lista = mo.equipos(df)
ultima = df["fecha"].max().strftime("%d/%m/%Y")

st.title("Modelo Poisson + Dixon-Coles — La Liga")
st.caption(f"{len(df)} partidos · ultimo partido cargado: {ultima}")

c1, c2, c3 = st.columns([2, 2, 1])
local = c1.selectbox("Local", lista, index=lista.index("Real Madrid") if "Real Madrid" in lista else 0)
visitante = c2.selectbox("Visitante", [e for e in lista if e != local])
mo.RHO = c3.number_input("ρ Dixon-Coles (solo goles)", value=-0.05, step=0.01, format="%.2f")

# ---- resumen de lambdas de todas las metricas
resumen = []
resultados = {}
for met in mo.METRICAS:
    r = mo.analizar(df, local, visitante, met)
    resultados[met] = r
    resumen.append({"Metrica": mo.NOMBRES[met],
                    f"λ {local}": round(r["lambda_local"], 2),
                    f"λ {visitante}": round(r["lambda_visitante"], 2),
                    "λ total": round(r["lambda_local"] + r["lambda_visitante"], 2)})
st.subheader("Esperados (λ) por metrica")
st.dataframe(pd.DataFrame(resumen).set_index("Metrica"), width="stretch")

# ---- detalle por metrica
st.subheader("Detalle por metrica")
tabs = st.tabs([mo.NOMBRES[m] for m in mo.METRICAS])
for tab, met in zip(tabs, mo.METRICAS):
    r = resultados[met]
    with tab:
        a, b = st.columns([1, 1])
        with a:
            st.markdown("**Mercados y cuota justa**")
            tabla = pd.DataFrame({
                "Mercado": list(r["mercados"].keys()),
                "Probabilidad": [f"{v:.1%}" for v in r["mercados"].values()],
                "Cuota justa": [mo.cuota_justa(v) for v in r["mercados"].values()],
            })
            st.dataframe(tabla, hide_index=True, width="stretch")
            st.markdown("**Fuerzas (1.00 = promedio de la liga)**")
            st.dataframe(r["fuerzas"].loc[[local, visitante]].round(2), width="stretch")
        with b:
            st.markdown(f"**Matriz de resultados** (filas = {local}, columnas = {visitante})")
            k = min(r["matriz"].shape[0], 8)
            m = pd.DataFrame(r["matriz"][:k, :k] * 100).round(1)
            st.dataframe(m.style.background_gradient(cmap="Blues").format("{:.1f}%"),
                         width="stretch")

st.caption("Peso por recencia: exp(-0.005 × dias). Fuente: football-data.co.uk, actualizado cada lunes por GitHub Actions.")

"""
diagnosticos_bayes.py — ¿Se puede confiar en las muestras del modelo bayesiano? Tres chequeos:

1. diagnosticar(): convergencia del muestreo (NUTS corre 4 cadenas independientes; si todas cuentan lo mismo, convergió)
     r_hat        cadenas de acuerdo entre sí. 1.00 perfecto; > 1.01 revisar; > 1.05 mal
     ess          muestras "efectivas": cuántas muestras independientes equivalen las 4000. > 400 bien; < 100 mal
     divergencias pasos donde el muestreador se perdió. 0 es lo esperado; > 1% del total mal
     bfmi         qué tan bien explora la energía. > 0.3 bien; < 0.2 mal
     prof_max     % de pasos que tocaron el tope de profundidad del árbol. > 5% = muestreo ineficiente (no incorrecto)
2. graficar(): traza (cada cadena debería verse como "pasto" mezclado, sin tendencias) y fuerzas por equipo con intervalo
3. chequeo_predictivo(): simula la liga completa desde el modelo y la compara con lo observado
     (promedios, dispersión, % local/empate/visita, % over, % ambos > 0). Si lo observado cae fuera del 90%
     simulado, el modelo no reproduce ese rasgo de los datos.
"""

import os

import numpy as np
import pandas as pd

VARS_LIGA = ["base", "ventaja_local", "sigma_ataque", "sigma_defensa"]
UMBRAL = {"rhat_revisar": 1.01, "rhat_mal": 1.05, "ess_revisar": 400, "ess_mal": 100,
          "div_mal_pct": 1.0, "bfmi_revisar": 0.3, "bfmi_mal": 0.2, "prof_revisar_pct": 5.0}


# ------------------------------------------------------------------ 1. convergencia
def diagnosticar(idata, datos: dict) -> dict:
    import arviz as az
    variables = VARS_LIGA + ["ataque", "defensa"] + (["rho"] if datos["dixon_coles"] else [])
    resumen = az.summary(idata, var_names=variables)
    ss = idata.sample_stats
    div = ss["diverging"].values
    energia = ss["energy"].values                                  # (cadena, muestra)
    bfmi = [np.var(np.diff(e)) / np.var(e) for e in energia]     # por cadena
    prof = float(ss["reached_max_treedepth"].values.mean() * 100) if "reached_max_treedepth" in ss else float("nan")

    d = {
        "rhat_max": float(resumen["r_hat"].max()),
        "ess_min": float(resumen[["ess_bulk", "ess_tail"]].min().min()),
        "divergencias": int(div.sum()), "pct_divergencias": float(div.mean() * 100),
        "bfmi_min": float(min(bfmi)), "pct_prof_max": prof,
        "n_muestras": int(div.size),
    }
    for v in VARS_LIGA + (["rho"] if datos["dixon_coles"] else []):
        d[v] = float(resumen.loc[v, "mean"])
        d[f"{v}_sd"] = float(resumen.loc[v, "sd"])
    d["veredicto"], d["motivos"] = veredicto(d)
    d["resumen"] = resumen
    return d


def veredicto(d: dict) -> tuple:
    u, mal, revisar = UMBRAL, [], []
    if d["rhat_max"] > u["rhat_mal"]:
        mal.append(f"cadenas en desacuerdo (r_hat {d['rhat_max']:.3f})")
    elif d["rhat_max"] > u["rhat_revisar"]:
        revisar.append(f"r_hat {d['rhat_max']:.3f} (ideal < 1.01)")
    if d["ess_min"] < u["ess_mal"]:
        mal.append(f"muy pocas muestras efectivas ({d['ess_min']:.0f})")
    elif d["ess_min"] < u["ess_revisar"]:
        revisar.append(f"muestras efectivas justas ({d['ess_min']:.0f}, ideal > 400): subir draws")
    if d["pct_divergencias"] > u["div_mal_pct"]:
        mal.append(f"{d['divergencias']} divergencias ({d['pct_divergencias']:.1f}%)")
    elif d["divergencias"] > 0:
        revisar.append(f"{d['divergencias']} divergencias: subir target_accept a 0.95")
    if d["bfmi_min"] < u["bfmi_mal"]:
        mal.append(f"bfmi {d['bfmi_min']:.2f}")
    elif d["bfmi_min"] < u["bfmi_revisar"]:
        revisar.append(f"bfmi {d['bfmi_min']:.2f} (ideal > 0.3)")
    if d["pct_prof_max"] > u["prof_revisar_pct"]:
        revisar.append(f"{d['pct_prof_max']:.0f}% de pasos al tope de profundidad (lento, no incorrecto)")
    if mal:
        return "MAL", "; ".join(mal + revisar)
    if revisar:
        return "REVISAR", "; ".join(revisar)
    return "OK", "todo dentro de rango"


# ------------------------------------------------------------------ 2. gráficas
def graficar(idata, datos: dict, muestras: dict, prefijo: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(os.path.dirname(prefijo) or ".", exist_ok=True)
    post, ss = idata.posterior, idata.sample_stats
    variables = VARS_LIGA + (["rho"] if datos["dixon_coles"] else [])
    filas = len(variables) + 1
    fig, ejes = plt.subplots(filas, 2, figsize=(11, 2.1 * filas))
    for i, v in enumerate(variables):
        arr = post[v].values                                      # (cadena, muestra)
        for c in range(arr.shape[0]):
            ejes[i, 0].hist(arr[c], bins=40, histtype="step", density=True)
            ejes[i, 1].plot(arr[c], lw=0.4, alpha=0.8)
        ejes[i, 0].set_title(f"{v}: distribución por cadena (deben coincidir)", fontsize=9)
        ejes[i, 1].set_title(f"{v}: traza por cadena (debe verse como pasto, sin tendencia)", fontsize=9)
    e = ss["energy"].values
    for c in range(e.shape[0]):
        ejes[-1, 0].hist(e[c] - e[c].mean(), bins=40, histtype="step", density=True, label="energía" if c == 0 else None)
        ejes[-1, 0].hist(np.diff(e[c]), bins=40, histtype="stepfilled", alpha=0.15, density=True, label="cambio de energía" if c == 0 else None)
        ejes[-1, 1].plot(e[c], lw=0.4, alpha=0.8)
    ejes[-1, 0].set_title("energía: las dos formas deben parecerse (BFMI)", fontsize=9)
    ejes[-1, 0].legend(fontsize=8)
    ejes[-1, 1].set_title("energía por paso", fontsize=9)
    fig.suptitle(f"{datos['metrica']} — {datos['n_partidos']} partidos, {len(datos['equipos'])} equipos", fontsize=11)
    fig.tight_layout()
    fig.savefig(f"{prefijo}_traza.png", dpi=110)
    plt.close(fig)

    # fuerzas por equipo (1.00 = promedio de la liga)
    a, d = np.exp(muestras["ataque"]), np.exp(muestras["defensa"])
    orden = np.argsort(a.mean(0))
    nombres = np.array(datos["equipos"])[orden]
    fig, ejes = plt.subplots(1, 2, figsize=(11, 0.28 * len(nombres) + 1.5), sharey=True)
    for eje, arr, titulo in [(ejes[0], a[:, orden], "Ataque (× promedio liga; > 1 = produce más)"),
                             (ejes[1], d[:, orden], "Defensa (× promedio liga; > 1 = concede más)")]:
        med, lo, hi = arr.mean(0), np.percentile(arr, 5, axis=0), np.percentile(arr, 95, axis=0)
        eje.errorbar(med, np.arange(len(nombres)), xerr=[med - lo, hi - med], fmt="o", ms=3, capsize=2)
        eje.axvline(1.0, color="gray", ls="--", lw=0.8)
        eje.set_title(titulo, fontsize=9)
        eje.grid(axis="x", alpha=0.3)
    ejes[0].set_yticks(np.arange(len(nombres)))
    ejes[0].set_yticklabels(nombres, fontsize=8)
    fig.suptitle(f"{datos['metrica']}: fuerzas por equipo con intervalo 5%–95%", fontsize=11)
    fig.tight_layout()
    fig.savefig(f"{prefijo}_equipos.png", dpi=110)
    plt.close(fig)


# ------------------------------------------------------------------ 3. chequeo predictivo
def _estadisticos(x: np.ndarray, y: np.ndarray, linea: float) -> dict:
    tot = x + y
    return {
        "media_local": x.mean(), "media_visita": y.mean(),
        "desv_local": x.std(), "desv_visita": y.std(),
        "pct_local_mas": (x > y).mean(), "pct_igual": (x == y).mean(), "pct_visita_mas": (x < y).mean(),
        f"pct_over_{linea}": (tot > linea).mean(), "pct_ambos_positivos": ((x > 0) & (y > 0)).mean(),
    }


def chequeo_predictivo(muestras: dict, datos: dict, n_sim: int = 300, semilla: int = 0) -> pd.DataFrame:
    """Simula todos los partidos de la liga n_sim veces (una por muestra del posterior) y compara con lo observado."""
    import modelo as mo
    rng = np.random.default_rng(semilla)
    x, y, i_l, i_v = datos["x"], datos["y"], datos["i_local"], datos["i_visita"]
    linea = round(float((x + y).mean())) - 0.5
    obs = _estadisticos(x, y, linea)
    sel = rng.choice(len(muestras["base"]), size=min(n_sim, len(muestras["base"])), replace=False)
    k_max = mo.K_MAX[datos["metrica"]]
    k = np.arange(k_max + 1)
    sims = []
    for s in sel:
        lam_l = np.exp(muestras["base"][s] + muestras["ventaja_local"][s] + muestras["ataque"][s][i_l] + muestras["defensa"][s][i_v])
        lam_v = np.exp(muestras["base"][s] + muestras["ataque"][s][i_v] + muestras["defensa"][s][i_l])
        if datos["dixon_coles"]:
            from modelo_bayes import matrices_muestras
            m = matrices_muestras(lam_l, lam_v, np.full(len(lam_l), muestras["rho"][s]), k_max, True)
            acum = m.reshape(len(lam_l), -1).cumsum(axis=1)
            idx = (acum < rng.random(len(lam_l))[:, None]).sum(axis=1)
            idx = np.minimum(idx, acum.shape[1] - 1)
            xs, ys = idx // (k_max + 1), idx % (k_max + 1)
        else:
            xs, ys = rng.poisson(lam_l), rng.poisson(lam_v)
        sims.append(_estadisticos(xs, ys, linea))
    sims = pd.DataFrame(sims)
    out = pd.DataFrame({
        "estadistico": list(obs), "observado": list(obs.values()),
        "simulado": sims.mean().values, "p05": sims.quantile(0.05).values, "p95": sims.quantile(0.95).values,
    })
    out["dentro"] = (out["observado"] >= out["p05"]) & (out["observado"] <= out["p95"])
    return out.round(3)

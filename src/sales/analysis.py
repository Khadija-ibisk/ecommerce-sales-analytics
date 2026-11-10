"""Analyses : exécution des requêtes SQL, segmentation RFM, cohortes et prévision."""
import sqlite3

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from . import config


# --------------------------------------------------------------------------- SQL
def split_queries(sql_text: str) -> dict:
    """Découpe un fichier SQL en requêtes nommées via `-- name: xxx`."""
    queries, name, buf = {}, None, []
    for line in sql_text.splitlines():
        if line.strip().lower().startswith("-- name:"):
            if name:
                queries[name] = "\n".join(buf).strip().rstrip(";")
            name, buf = line.split(":", 1)[1].strip(), []
        elif name:
            buf.append(line)
    if name:
        queries[name] = "\n".join(buf).strip().rstrip(";")
    return {k: v for k, v in queries.items() if v}


def run_queries(db_path=None) -> dict:
    sql_text = (config.SQL_DIR / "analytics.sql").read_text(encoding="utf-8")
    with sqlite3.connect(db_path or config.DB_FILE) as conn:
        return {name: pd.read_sql_query(q, conn) for name, q in split_queries(sql_text).items()}


# --------------------------------------------------------------------------- RFM
def rfm_segment(r: int, f: int, m: int) -> str:
    if r >= 4 and f >= 4:
        return "Champions"
    if f >= 4:
        return "Clients fidèles"
    if r >= 4 and f <= 2:
        return "Nouveaux / prometteurs"
    if r <= 2 and (f >= 3 or m >= 4):
        return "À risque (à réactiver)"
    if r <= 2:
        return "Perdus"
    return "À surveiller"


def rfm_segments(rfm: pd.DataFrame) -> pd.DataFrame:
    rfm = rfm.copy()
    rfm["segment"] = [rfm_segment(r, f, m) for r, f, m in zip(rfm.score_r, rfm.score_f, rfm.score_m)]
    summary = (
        rfm.groupby("segment")
        .agg(nb_clients=("customer_id", "count"),
             recence_moy_jours=("recence_jours", "mean"),
             frequence_moy=("frequence", "mean"),
             ca_total=("montant", "sum"))
        .sort_values("ca_total", ascending=False)
    )
    summary["part_clients_pct"] = 100 * summary["nb_clients"] / summary["nb_clients"].sum()
    summary["part_ca_pct"] = 100 * summary["ca_total"] / summary["ca_total"].sum()
    return summary.round(1).reset_index()


# --------------------------------------------------------------------------- Cohortes
def cohort_retention(cohorts: pd.DataFrame, max_months: int = 12) -> pd.DataFrame:
    """Matrice de rétention : % de clients d'une cohorte actifs N mois après leur 1er achat."""
    df = cohorts.copy()
    c = pd.PeriodIndex(df["cohorte"], freq="M")
    a = pd.PeriodIndex(df["mois_activite"], freq="M")
    df["mois_ecart"] = (a.year - c.year) * 12 + (a.month - c.month)
    matrix = df.pivot_table(index="cohorte", columns="mois_ecart", values="clients_actifs", aggfunc="sum")
    retention = matrix.div(matrix[0], axis=0).mul(100)
    retention = retention.loc[:, [m for m in retention.columns if m <= max_months]]
    return retention.loc[retention.index < "2024-01"]  # cohortes 2023 : 12 mois de recul


# --------------------------------------------------------------------------- Prévision
def _design(months: pd.PeriodIndex, t0: pd.Period) -> np.ndarray:
    t = np.array([(p.year - t0.year) * 12 + (p.month - t0.month) for p in months], dtype=float)
    month_dummies = np.zeros((len(months), 11))
    for i, p in enumerate(months):
        if p.month > 1:
            month_dummies[i, p.month - 2] = 1
    return np.column_stack([t, month_dummies])


def forecast_revenue(monthly: pd.DataFrame, horizon: int = 12, holdout: int = 6) -> dict:
    """Régression tendance + saisonnalité mensuelle sur le log du CA.

    1. Validation : apprentissage sans les `holdout` derniers mois, mesure du MAPE.
    2. Prévision : réapprentissage sur tout l'historique, projection sur `horizon` mois.
    """
    months = pd.PeriodIndex(monthly["mois"], freq="M")
    y = np.log(monthly["chiffre_affaires"].values)
    t0 = months[0]
    X = _design(months, t0)

    val_model = LinearRegression().fit(X[:-holdout], y[:-holdout])
    pred_val = np.exp(val_model.predict(X[-holdout:]))
    actual_val = np.exp(y[-holdout:])
    mape = float(np.mean(np.abs(pred_val - actual_val) / actual_val) * 100)

    model = LinearRegression().fit(X, y)
    future = pd.period_range(months[-1] + 1, periods=horizon, freq="M")
    pred = np.exp(model.predict(_design(future, t0)))
    residual_std = float(np.std(y - model.predict(X)))

    forecast = pd.DataFrame(
        {
            "mois": future.astype(str),
            "prevision": pred.round(0),
            "borne_basse": (pred * np.exp(-1.96 * residual_std)).round(0),
            "borne_haute": (pred * np.exp(1.96 * residual_std)).round(0),
        }
    )
    return {
        "forecast": forecast,
        "mape_validation_pct": round(mape, 2),
        "croissance_mensuelle_tendance_pct": round(float(np.expm1(model.coef_[0]) * 100), 2),
        "ca_prevu_total": float(forecast["prevision"].sum()),
    }

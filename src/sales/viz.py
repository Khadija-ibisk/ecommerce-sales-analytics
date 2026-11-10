"""Graphiques du rapport (matplotlib, rendu sans écran)."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from . import config

BLUE, ORANGE, GREY, GREEN = "#2F6690", "#F28E2B", "#9AA5B1", "#59A14F"
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.alpha": 0.3, "font.size": 10})

euros = mticker.FuncFormatter(lambda v, _: f"{v / 1000:,.0f} k€".replace(",", " "))


def _save(fig, name: str) -> str:
    fig.tight_layout()
    fig.savefig(config.FIGURES_DIR / name, dpi=120)
    plt.close(fig)
    return f"figures/{name}"


def revenue_and_forecast(monthly: pd.DataFrame, forecast: pd.DataFrame) -> str:
    hist_x = pd.PeriodIndex(monthly["mois"], freq="M").to_timestamp()
    fut_x = pd.PeriodIndex(forecast["mois"], freq="M").to_timestamp()
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(hist_x, monthly["chiffre_affaires"], marker="o", color=BLUE, label="CA réalisé")
    ax.plot(fut_x, forecast["prevision"], marker="o", ls="--", color=ORANGE, label="Prévision 2025")
    ax.fill_between(fut_x, forecast["borne_basse"], forecast["borne_haute"], color=ORANGE, alpha=0.15,
                    label="Intervalle à 95 %")
    ax.yaxis.set_major_formatter(euros)
    ax.set_title("Chiffre d'affaires mensuel 2023-2024 et prévision 2025")
    ax.legend(loc="upper left")
    return _save(fig, "01_ca_mensuel_prevision.png")


def category_growth(df: pd.DataFrame) -> str:
    x = np.arange(len(df))
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar(x - 0.2, df["ca_2023"], 0.4, color=GREY, label="2023")
    ax.bar(x + 0.2, df["ca_2024"], 0.4, color=BLUE, label="2024")
    for i, g in enumerate(df["croissance_pct"]):
        ax.text(i + 0.2, df["ca_2024"].iloc[i], f"{g:+.0f} %", ha="center", va="bottom", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(df["categorie"])
    ax.yaxis.set_major_formatter(euros)
    ax.set_title("Chiffre d'affaires par catégorie : 2023 vs 2024")
    ax.legend()
    return _save(fig, "02_ca_categories.png")


def top_products(df: pd.DataFrame) -> str:
    df = df.iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.barh(df["produit"], df["chiffre_affaires"], color=BLUE)
    ax.xaxis.set_major_formatter(euros)
    ax.set_title("Top 10 des produits en 2024")
    return _save(fig, "03_top_produits.png")


def rfm_chart(summary: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = np.arange(len(summary))
    ax.bar(x - 0.2, summary["part_clients_pct"], 0.4, color=GREY, label="% des clients")
    ax.bar(x + 0.2, summary["part_ca_pct"], 0.4, color=GREEN, label="% du CA")
    ax.set_xticks(x)
    ax.set_xticklabels(summary["segment"], rotation=15, ha="right")
    ax.set_ylabel("%")
    ax.set_title("Segmentation RFM : poids en clients vs poids en chiffre d'affaires")
    ax.legend()
    return _save(fig, "04_segments_rfm.png")


def cohort_heatmap(retention: pd.DataFrame) -> str:
    data = retention.iloc[:, 1:]  # le mois 0 vaut toujours 100 %
    fig, ax = plt.subplots(figsize=(11, 5))
    im = ax.imshow(data.values, cmap="Blues", aspect="auto", vmin=0)
    ax.set_xticks(range(data.shape[1]))
    ax.set_xticklabels([f"M+{c}" for c in data.columns])
    ax.set_yticks(range(data.shape[0]))
    ax.set_yticklabels(data.index)
    ax.grid(False)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            v = data.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=8,
                        color="white" if v > np.nanmax(data.values) * 0.6 else "black")
    fig.colorbar(im, ax=ax, label="% de clients actifs")
    ax.set_title("Rétention par cohorte de premier achat (clients 2023)")
    return _save(fig, "05_cohortes.png")


def returns_chart(df: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(df["categorie"], df["taux_retour_pct"], color=ORANGE)
    ax.set_ylabel("Taux de retour (%)")
    ax.set_title("Taux de retour par catégorie")
    return _save(fig, "06_taux_retour.png")


def make_all(q: dict, rfm_summary: pd.DataFrame, retention: pd.DataFrame, forecast: pd.DataFrame) -> list:
    config.ensure_dirs()
    return [
        revenue_and_forecast(q["ca_mensuel"], forecast),
        category_growth(q["croissance_categories"]),
        top_products(q["top_produits_2024"]),
        rfm_chart(rfm_summary),
        cohort_heatmap(retention),
        returns_chart(q["taux_retour_categories"]),
    ]

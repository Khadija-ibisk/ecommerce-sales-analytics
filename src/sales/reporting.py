"""Génération du rapport Markdown et du tableau de bord HTML autonome."""
import base64
import html
import json

import pandas as pd

from . import config


def fmt_eur(v: float) -> str:
    return f"{v:,.0f} €".replace(",", " ")


def to_markdown(df: pd.DataFrame) -> str:
    def cell(v):
        return f"{v:,.2f}".replace(",", " ") if isinstance(v, float) else str(v)

    rows = ["| " + " | ".join(map(str, df.columns)) + " |", "| " + " | ".join("---" for _ in df.columns) + " |"]
    rows += ["| " + " | ".join(cell(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(rows)


def key_figures(q: dict, fc: dict) -> dict:
    k = q["kpis_annuels"].set_index("annee")
    y23, y24 = k.loc[2023], k.loc[2024]
    return {
        "ca_2024": float(y24["chiffre_affaires"]),
        "croissance_ca_pct": round(100 * (y24["chiffre_affaires"] / y23["chiffre_affaires"] - 1), 1),
        "marge_2024_pct": float(y24["taux_marge_pct"]),
        "commandes_2024": int(y24["nb_commandes"]),
        "clients_actifs_2024": int(y24["nb_clients_actifs"]),
        "panier_moyen_2024": float(y24["panier_moyen"]),
        "ca_prevu_2025": fc["ca_prevu_total"],
        "mape_prevision_pct": fc["mape_validation_pct"],
    }


def recommendations(q: dict, rfm: pd.DataFrame) -> list:
    cat = q["croissance_categories"].sort_values("croissance_pct", ascending=False)
    ret = q["taux_retour_categories"].iloc[0]
    chan = q["canaux_acquisition"].iloc[0]
    seg = rfm.set_index("segment")
    risk = seg.loc["À risque (à réactiver)"] if "À risque (à réactiver)" in seg.index else None
    champions = seg.loc["Champions"] if "Champions" in seg.index else None
    recos = [
        f"**Renforcer la catégorie {cat.iloc[0]['categorie']}** (croissance de {cat.iloc[0]['croissance_pct']:+.0f} % "
        f"en 2024) et analyser le recul relatif de **{cat.iloc[-1]['categorie']}** ({cat.iloc[-1]['croissance_pct']:+.0f} %).",
        f"**Réduire les retours en {ret['categorie']}** ({ret['taux_retour_pct']:.1f} % des lignes) : guide des tailles, "
        "photos et avis clients.",
        f"**Investir davantage dans le canal « {chan['canal']} »**, qui apporte les clients à la plus forte valeur "
        f"({fmt_eur(chan['valeur_client_moyenne'])} en moyenne).",
        "**Anticiper les pics de novembre-décembre** (stocks, logistique, service client) : ce sont les deux mois "
        "les plus forts selon la prévision 2025.",
    ]
    if risk is not None:
        recos.append(
            f"**Lancer une campagne de réactivation** auprès des {int(risk['nb_clients'])} clients « à risque », "
            f"qui pèsent {risk['part_ca_pct']:.0f} % du CA historique."
        )
    if champions is not None:
        recos.append(
            f"**Créer un programme de fidélité** pour les {int(champions['nb_clients'])} « Champions » "
            f"({champions['part_clients_pct']:.0f} % des clients, {champions['part_ca_pct']:.0f} % du CA)."
        )
    return recos


def write_markdown(quality: dict, q: dict, rfm: pd.DataFrame, fc: dict, figures: list, kf: dict) -> None:
    lines = [
        "# Rapport d'analyse des ventes e-commerce 2023-2024",
        "",
        f"_Édité le {config.report_date_fr()} – données du 1er janvier 2023 au 31 décembre 2024._",
        "",
        "## 1. Synthèse",
        "",
        f"- Chiffre d'affaires 2024 : **{fmt_eur(kf['ca_2024'])}** ({kf['croissance_ca_pct']:+.1f} % vs 2023).",
        f"- Taux de marge brute : **{kf['marge_2024_pct']:.1f} %** – panier moyen : **{fmt_eur(kf['panier_moyen_2024'])}**.",
        f"- **{kf['clients_actifs_2024']} clients actifs** et **{kf['commandes_2024']} commandes** en 2024.",
        f"- Prévision 2025 : **{fmt_eur(kf['ca_prevu_2025'])}** (erreur moyenne de validation : "
        f"{kf['mape_prevision_pct']:.1f} %).",
        "",
        "## 2. Qualité des données et ETL",
        "",
        to_markdown(pd.DataFrame([quality])),
        "",
        "## 3. Évolution des ventes",
        "",
        to_markdown(q["kpis_annuels"]),
        "",
        f"![CA mensuel]({figures[0]})",
        "",
        "## 4. Catégories et produits",
        "",
        to_markdown(q["croissance_categories"]),
        "",
        f"![Catégories]({figures[1]})",
        f"![Top produits]({figures[2]})",
        "",
        to_markdown(q["taux_retour_categories"]),
        "",
        f"![Retours]({figures[5]})",
        "",
        "## 5. Clients",
        "",
        "### Segmentation RFM",
        "",
        to_markdown(rfm),
        "",
        f"![RFM]({figures[3]})",
        "",
        "### Rétention par cohorte",
        "",
        f"![Cohortes]({figures[4]})",
        "",
        "### Canaux d'acquisition",
        "",
        to_markdown(q["canaux_acquisition"]),
        "",
        "## 6. Prévision 2025",
        "",
        to_markdown(fc["forecast"]),
        "",
        "## 7. Recommandations",
        "",
    ]
    lines += [f"{i}. {r}" for i, r in enumerate(recommendations(q, rfm), 1)]
    (config.REPORTS_DIR / "rapport.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _img(path: str) -> str:
    data = base64.b64encode((config.REPORTS_DIR / path).read_bytes()).decode()
    return f'<img src="data:image/png;base64,{data}" alt="{html.escape(path)}">'


def write_dashboard(q: dict, rfm: pd.DataFrame, figures: list, kf: dict) -> None:
    cards = [
        ("CA 2024", fmt_eur(kf["ca_2024"]), f"{kf['croissance_ca_pct']:+.1f} % vs 2023"),
        ("Marge brute", f"{kf['marge_2024_pct']:.1f} %", "du CA 2024"),
        ("Commandes 2024", f"{kf['commandes_2024']:,}".replace(",", " "), f"panier moyen {fmt_eur(kf['panier_moyen_2024'])}"),
        ("Clients actifs", f"{kf['clients_actifs_2024']:,}".replace(",", " "), "en 2024"),
        ("Prévision 2025", fmt_eur(kf["ca_prevu_2025"]), f"MAPE validation {kf['mape_prevision_pct']:.1f} %"),
    ]
    cards_html = "".join(
        f'<div class="card"><div class="label">{l}</div><div class="value">{v}</div><div class="sub">{s}</div></div>'
        for l, v, s in cards
    )
    charts_html = "".join(f'<div class="chart">{_img(f)}</div>' for f in figures)
    table = rfm.to_html(index=False, classes="tbl", float_format=lambda v: f"{v:,.1f}".replace(",", " "))
    recos = "".join(f"<li>{r}</li>" for r in recommendations(q, rfm))
    recos = recos.replace("**", "")  # pas de Markdown dans le HTML
    page = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tableau de bord – Ventes e-commerce</title>
<style>
 body{{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f4f6f8;color:#1f2933}}
 header{{background:#2F6690;color:#fff;padding:24px 32px}} header p{{margin:4px 0 0;opacity:.85}}
 main{{max-width:1200px;margin:auto;padding:24px}}
 .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px}}
 .card{{background:#fff;border-radius:10px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
 .label{{font-size:13px;color:#52606d}} .value{{font-size:26px;font-weight:600;margin:6px 0}} .sub{{font-size:12px;color:#7b8794}}
 .charts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(520px,1fr));gap:16px;margin-top:24px}}
 .chart{{background:#fff;border-radius:10px;padding:8px}} .chart img{{width:100%}}
 section{{background:#fff;border-radius:10px;padding:16px 24px;margin-top:24px}}
 .tbl{{border-collapse:collapse;width:100%;font-size:14px}} .tbl th,.tbl td{{padding:6px 10px;border-bottom:1px solid #e4e7eb;text-align:right}}
 .tbl th:first-child,.tbl td:first-child{{text-align:left}}
 footer{{text-align:center;color:#7b8794;font-size:12px;padding:24px}}
</style></head><body>
<header><h1>Tableau de bord – Ventes e-commerce 2023-2024</h1>
<p>Édité le {config.report_date_fr()}</p></header>
<main>
<div class="cards">{cards_html}</div>
<div class="charts">{charts_html}</div>
<section><h2>Segments RFM</h2>{table}</section>
<section><h2>Recommandations</h2><ol>{recos}</ol></section>
</main>
<footer>Données synthétiques – projet d'analyse de données ({config.REPORT_DATE.year})</footer>
</body></html>"""
    (config.REPORTS_DIR / "dashboard.html").write_text(page, encoding="utf-8")


def write_metrics(kf: dict) -> None:
    out = dict(kf, date_edition=config.REPORT_DATE.isoformat())
    (config.REPORTS_DIR / "metrics.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

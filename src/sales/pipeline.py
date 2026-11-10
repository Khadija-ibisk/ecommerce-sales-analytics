"""Pipeline complet : génération -> ETL -> entrepôt SQL -> analyses -> rapports."""
import time

import pandas as pd

from . import analysis, config, data_generation, etl, reporting, viz


def run() -> dict:
    t0 = time.time()
    config.ensure_dirs()

    print("1/6 Génération des données brutes…")
    data_generation.save_raw(data_generation.generate_all())

    print("2/6 Extraction et nettoyage…")
    raw = {name: pd.read_csv(config.RAW_DIR / f"{name}.csv") for name in ("customers", "products", "order_lines")}
    star = etl.build_star_schema(raw)
    quality = etl.quality_report(raw, star)

    print("3/6 Chargement de l'entrepôt SQLite (schéma en étoile)…")
    etl.load_warehouse(star)

    print("4/6 Requêtes analytiques SQL…")
    q = analysis.run_queries()

    print("5/6 RFM, cohortes et prévision…")
    rfm = analysis.rfm_segments(q["rfm_base"])
    retention = analysis.cohort_retention(q["cohortes"])
    fc = analysis.forecast_revenue(q["ca_mensuel"])

    print("6/6 Graphiques, rapport et tableau de bord…")
    figures = viz.make_all(q, rfm, retention, fc["forecast"])
    kf = reporting.key_figures(q, fc)
    reporting.write_markdown(quality, q, rfm, fc, figures, kf)
    reporting.write_dashboard(q, rfm, figures, kf)
    reporting.write_metrics(kf)

    print(f"\nTerminé en {time.time() - t0:.1f}s")
    for k, v in kf.items():
        print(f"  {k:<22} {v}")
    return kf

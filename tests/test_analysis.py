import pandas as pd

from sales import analysis, reporting, viz


def test_split_queries():
    q = analysis.split_queries("-- name: a\nSELECT 1;\n-- name: b\n-- commentaire\nSELECT 2;\n")
    assert list(q) == ["a", "b"]
    assert q["a"] == "SELECT 1"


def test_sql_queries(warehouse, star):
    q = analysis.run_queries(warehouse)
    k = q["kpis_annuels"]
    assert list(k["annee"]) == [2023, 2024]
    assert k.loc[1, "chiffre_affaires"] > k.loc[0, "chiffre_affaires"]  # croissance simulée

    delivered = star["fact_sales"].query("status == 'Livrée'")["net_amount"].sum()
    assert abs(q["ca_mensuel"]["chiffre_affaires"].sum() - delivered) < 1

    assert len(q["ca_mensuel"]) == 24
    assert len(q["top_produits_2024"]) == 10
    rfm = q["rfm_base"]
    assert rfm[["score_r", "score_f", "score_m"]].isin(range(1, 6)).all().all()


def test_rfm_segments(warehouse):
    q = analysis.run_queries(warehouse)
    seg = analysis.rfm_segments(q["rfm_base"])
    assert abs(seg["part_clients_pct"].sum() - 100) < 0.5
    assert "Champions" in set(seg["segment"])
    champions = seg.set_index("segment").loc["Champions"]
    assert champions["part_ca_pct"] > champions["part_clients_pct"]


def test_cohort_retention(warehouse):
    q = analysis.run_queries(warehouse)
    ret = analysis.cohort_retention(q["cohortes"])
    assert len(ret) == 12
    assert (ret[0] == 100).all()
    assert (ret.drop(columns=0).max().max()) < 100


def test_forecast():
    months = pd.period_range("2023-01", periods=24, freq="M")
    base = [100 + 3 * i + (40 if m.month == 12 else 0) for i, m in enumerate(months)]
    fc = analysis.forecast_revenue(pd.DataFrame({"mois": months.astype(str), "chiffre_affaires": base}))
    f = fc["forecast"]
    assert len(f) == 12 and f["mois"].iloc[0] == "2025-01"
    assert (f["borne_basse"] <= f["prevision"]).all() and (f["prevision"] <= f["borne_haute"]).all()
    assert f.set_index("mois").loc["2025-12", "prevision"] == f["prevision"].max()
    assert fc["mape_validation_pct"] < 10


def test_reports_are_written(warehouse, tmp_reports):
    q = analysis.run_queries(warehouse)
    rfm = analysis.rfm_segments(q["rfm_base"])
    ret = analysis.cohort_retention(q["cohortes"])
    fc = analysis.forecast_revenue(q["ca_mensuel"])
    figures = viz.make_all(q, rfm, ret, fc["forecast"])
    kf = reporting.key_figures(q, fc)
    reporting.write_markdown({"ok": 1}, q, rfm, fc, figures, kf)
    reporting.write_dashboard(q, rfm, figures, kf)

    assert all((tmp_reports / f).exists() for f in figures)
    md = (tmp_reports / "rapport.md").read_text(encoding="utf-8")
    assert "2025" in md and "## 7. Recommandations" in md
    page = (tmp_reports / "dashboard.html").read_text(encoding="utf-8")
    assert page.count("data:image/png;base64") == 6

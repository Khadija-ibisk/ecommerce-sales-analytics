import pandas as pd

from sales import data_generation, etl


def test_generation_is_reproducible():
    a = data_generation.generate_all(seed=5)["order_lines"]
    b = data_generation.generate_all(seed=5)["order_lines"]
    pd.testing.assert_frame_equal(a, b)


def test_parse_dates_handles_both_formats():
    out = etl.parse_dates(pd.Series(["2024-03-01", "01/03/2024", "n'importe quoi"]))
    assert out.iloc[0] == out.iloc[1] == pd.Timestamp("2024-03-01")
    assert pd.isna(out.iloc[2])


def test_raw_data_has_quality_issues(raw):
    lines = raw["order_lines"]
    assert lines.duplicated(["order_id", "line_number"]).any()
    assert lines["unit_price"].astype(str).str.contains(",").any()
    assert (lines["quantity"] < 0).any()
    assert raw["customers"]["city"].isna().any()


def test_fact_table_is_clean(star):
    fact = star["fact_sales"]
    assert not fact.duplicated(["order_id", "line_number"]).any()
    assert (fact["quantity"] > 0).all()
    assert set(fact["status"]) <= {"Livrée", "Retournée", "Annulée"}
    assert fact.notna().all().all()


def test_referential_integrity(star):
    fact = star["fact_sales"]
    assert fact["customer_id"].isin(star["dim_customer"]["customer_id"]).all()
    assert fact["product_id"].isin(star["dim_product"]["product_id"]).all()
    assert fact["date_key"].isin(star["dim_date"]["date_key"]).all()


def test_cities_are_normalised(star):
    cities = set(star["dim_customer"]["city"])
    assert all(c == c.strip() and not c.isupper() for c in cities)
    assert "Inconnue" in cities


def test_quality_report(raw, star):
    rep = etl.quality_report(raw, star)
    assert rep["doublons_supprimes"] > 0
    assert rep["lignes_chargees"] == rep["lignes_brutes"] - rep["doublons_supprimes"]

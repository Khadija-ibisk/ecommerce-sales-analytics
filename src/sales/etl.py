"""ETL : nettoyage des fichiers bruts et chargement d'un entrepôt en étoile (SQLite)."""
import sqlite3

import numpy as np
import pandas as pd

from . import config

STATUSES = {"livrée": "Livrée", "retournée": "Retournée", "annulée": "Annulée"}


def parse_dates(s: pd.Series) -> pd.Series:
    """Gère les deux formats rencontrés : AAAA-MM-JJ et JJ/MM/AAAA."""
    iso = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")
    fr = pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")
    return iso.fillna(fr)


def clean_customers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates("customer_id").copy()
    df["city"] = df["city"].astype("string").str.strip().str.title().fillna("Inconnue")
    df["region"] = df["city"].map(config.REGIONS).fillna("Inconnue")
    df["age_band"] = pd.cut(df["age"], [17, 24, 34, 44, 54, 64, 120],
                            labels=["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]).astype(str)
    return df.reset_index(drop=True)


def clean_order_lines(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates(["order_id", "line_number"]).copy()
    df["order_date"] = parse_dates(df["order_date"].astype(str))
    df["unit_price"] = pd.to_numeric(df["unit_price"].astype(str).str.replace(",", ".", regex=False))
    df["quantity"] = df["quantity"].abs()
    df["status"] = df["status"].str.strip().str.lower().map(STATUSES)
    df = df.dropna(subset=["order_date", "status"])
    df["gross_amount"] = (df["unit_price"] * df["quantity"]).round(2)
    df["net_amount"] = (df["gross_amount"] * (1 - df["discount_pct"] / 100)).round(2)
    return df.reset_index(drop=True)


def build_dim_date(dates: pd.Series) -> pd.DataFrame:
    days = pd.date_range(dates.min(), dates.max(), freq="D")
    return pd.DataFrame(
        {
            "date_key": days.strftime("%Y%m%d").astype(int),
            "full_date": days.strftime("%Y-%m-%d"),
            "year": days.year,
            "quarter": days.quarter,
            "month": days.month,
            "month_name": [config.MONTHS_FR[m - 1] for m in days.month],
            "year_month": days.strftime("%Y-%m"),
            "weekday": days.weekday + 1,
            "is_weekend": (days.weekday >= 5).astype(int),
        }
    )


def build_star_schema(raw: dict) -> dict:
    customers = clean_customers(raw["customers"])
    lines = clean_order_lines(raw["order_lines"])
    products = raw["products"].drop_duplicates("product_id").reset_index(drop=True)

    # Seuls les clients et produits connus sont chargés (intégrité référentielle)
    lines = lines[lines["customer_id"].isin(customers["customer_id"]) & lines["product_id"].isin(products["product_id"])]

    unit_cost = lines["product_id"].map(products.set_index("product_id")["unit_cost"])
    fact = pd.DataFrame(
        {
            "order_id": lines["order_id"],
            "line_number": lines["line_number"],
            "date_key": lines["order_date"].dt.strftime("%Y%m%d").astype(int),
            "customer_id": lines["customer_id"],
            "product_id": lines["product_id"],
            "payment_method": lines["payment_method"],
            "status": lines["status"],
            "quantity": lines["quantity"],
            "unit_price": lines["unit_price"],
            "discount_pct": lines["discount_pct"],
            "net_amount": lines["net_amount"],
            "margin": np.round(lines["net_amount"] - unit_cost * lines["quantity"], 2),
        }
    )
    dim_customer = customers[["customer_id", "gender", "age", "age_band", "city", "region", "acquisition_channel"]]
    return {
        "dim_date": build_dim_date(lines["order_date"]),
        "dim_customer": dim_customer,
        "dim_product": products,
        "fact_sales": fact.reset_index(drop=True),
    }


def quality_report(raw: dict, star: dict) -> dict:
    lines = raw["order_lines"]
    return {
        "lignes_brutes": int(len(lines)),
        "doublons_supprimes": int(lines.duplicated(["order_id", "line_number"]).sum()),
        "dates_format_fr_corrigees": int(lines["order_date"].astype(str).str.contains("/").sum()),
        "prix_avec_virgule_corriges": int(lines["unit_price"].astype(str).str.contains(",").sum()),
        "quantites_negatives_corrigees": int((pd.to_numeric(lines["quantity"]) < 0).sum()),
        "villes_manquantes": int(raw["customers"]["city"].isna().sum()),
        "lignes_chargees": int(len(star["fact_sales"])),
    }


def load_warehouse(star: dict, db_path=None) -> None:
    db_path = db_path or config.DB_FILE
    ddl = (config.SQL_DIR / "schema.sql").read_text(encoding="utf-8")
    with sqlite3.connect(db_path) as conn:
        conn.executescript(ddl)
        for table in ("dim_date", "dim_customer", "dim_product", "fact_sales"):
            star[table].to_sql(table, conn, if_exists="append", index=False)

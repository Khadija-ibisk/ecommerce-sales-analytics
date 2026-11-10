"""Génération de données e-commerce synthétiques (clients, produits, commandes 2023-2024).

Les fichiers bruts contiennent volontairement des défauts réalistes : doublons,
formats de date mixtes, décimales avec virgule, villes manquantes, quantités
négatives et casse incohérente.
"""
import numpy as np
import pandas as pd

from . import config


def generate_products(rng: np.random.Generator) -> pd.DataFrame:
    cats = list(config.CATEGORIES)
    category = rng.choice(cats, size=config.N_PRODUCTS, p=[0.15, 0.2, 0.25, 0.15, 0.15, 0.1])
    mean_price = np.array([config.CATEGORIES[c][0] for c in category])
    margin = np.array([config.CATEGORIES[c][1] for c in category])
    price = np.round(mean_price * rng.lognormal(0, 0.4, size=config.N_PRODUCTS), 2)
    cost = np.round(price * (1 - margin * rng.uniform(0.8, 1.2, size=config.N_PRODUCTS)), 2)
    return pd.DataFrame(
        {
            "product_id": [f"P{i:04d}" for i in range(1, config.N_PRODUCTS + 1)],
            "product_name": [f"{c} – article {i}" for i, c in enumerate(category, 1)],
            "category": category,
            "unit_price": price,
            "unit_cost": cost,
        }
    )


def generate_customers(rng: np.random.Generator) -> pd.DataFrame:
    n = config.N_CUSTOMERS
    cities = list(config.REGIONS)
    return pd.DataFrame(
        {
            "customer_id": [f"CL{i:05d}" for i in range(1, n + 1)],
            "gender": rng.choice(["F", "H"], size=n, p=[0.56, 0.44]),
            "age": rng.integers(18, 75, size=n),
            "city": rng.choice(cities, size=n, p=[0.25, 0.12, 0.1, 0.09, 0.08, 0.08, 0.08, 0.07, 0.07, 0.06]),
            "acquisition_channel": rng.choice(
                ["SEO", "Réseaux sociaux", "Publicité", "Parrainage", "Email"], size=n, p=[0.3, 0.25, 0.2, 0.1, 0.15]
            ),
        }
    )


def generate_orders(rng, customers: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    days = pd.date_range(config.START_DATE, config.END_DATE, freq="D")
    t = np.arange(len(days)) / 365
    month = days.month.values
    seasonality = np.select(
        [month == 11, month == 12, np.isin(month, [1, 7]), np.isin(month, [2, 8])],
        [1.6, 1.9, 1.25, 0.8],
        default=1.0,
    )
    weekday = np.where(days.weekday.values >= 5, 1.2, 1.0)
    lam = 22 * (1 + 0.18 * t) * seasonality * weekday
    n_per_day = rng.poisson(lam).astype(np.intp)

    order_dates = np.repeat(days.values, n_per_day)
    n_orders = len(order_dates)

    # Les clients ont des propensions d'achat très différentes (loi de Pareto)
    weights = rng.pareto(1.3, size=len(customers)) + 0.05
    cust = rng.choice(customers["customer_id"].values, size=n_orders, p=weights / weights.sum())

    orders = pd.DataFrame(
        {
            "order_id": [f"CMD{i:06d}" for i in range(1, n_orders + 1)],
            "order_date": order_dates,
            "customer_id": cust,
            "payment_method": rng.choice(["Carte", "PayPal", "Virement", "Paiement en 3x"], size=n_orders,
                                         p=[0.55, 0.25, 0.05, 0.15]),
        }
    )

    # Lignes de commande : 1 à 4 articles par commande
    n_lines = rng.choice([1, 2, 3, 4], size=n_orders, p=[0.55, 0.28, 0.12, 0.05]).astype(np.intp)
    lines = orders.loc[orders.index.repeat(n_lines)].reset_index(drop=True)
    popularity = rng.pareto(1.5, size=len(products)) + 0.1
    pidx = rng.choice(len(products), size=len(lines), p=popularity / popularity.sum())
    lines["product_id"] = products["product_id"].values[pidx]
    lines["unit_price"] = products["unit_price"].values[pidx]
    lines["quantity"] = rng.choice([1, 1, 1, 1, 2, 2, 3], size=len(lines))
    is_promo = np.isin(pd.DatetimeIndex(lines["order_date"]).month, [1, 7, 11])
    lines["discount_pct"] = np.where(is_promo, rng.choice([0, 10, 20, 30], size=len(lines)), 0)
    return_rate = np.where(products["category"].values[pidx] == "Mode", 0.12, 0.04)
    u = rng.uniform(size=len(lines))
    lines["status"] = np.where(u < 0.02, "Annulée", np.where(u < 0.02 + return_rate, "Retournée", "Livrée"))
    lines.insert(1, "line_number", lines.groupby("order_id").cumcount() + 1)
    return lines


def inject_quality_issues(rng, customers: pd.DataFrame, lines: pd.DataFrame):
    customers = customers.copy()
    lines = lines.copy()

    idx = rng.choice(len(customers), size=40, replace=False)
    customers.loc[idx, "city"] = np.nan
    idx = rng.choice(len(customers), size=60, replace=False)
    customers.loc[idx, "city"] = customers.loc[idx, "city"].str.upper() + "  "

    lines["order_date"] = pd.to_datetime(lines["order_date"]).dt.strftime("%Y-%m-%d").astype(object)
    idx = rng.choice(len(lines), size=int(0.03 * len(lines)), replace=False)
    lines.loc[idx, "order_date"] = pd.to_datetime(lines.loc[idx, "order_date"]).dt.strftime("%d/%m/%Y")

    lines["unit_price"] = lines["unit_price"].map(lambda v: f"{v:.2f}").astype(object)
    idx = rng.choice(len(lines), size=int(0.05 * len(lines)), replace=False)
    lines.loc[idx, "unit_price"] = lines.loc[idx, "unit_price"].str.replace(".", ",", regex=False)

    idx = rng.choice(len(lines), size=25, replace=False)
    lines.loc[idx, "quantity"] = -lines.loc[idx, "quantity"]

    idx = rng.choice(len(lines), size=int(0.02 * len(lines)), replace=False)
    lines.loc[idx, "status"] = lines.loc[idx, "status"].str.lower()

    dup = lines.sample(n=int(0.01 * len(lines)), random_state=3)
    lines = pd.concat([lines, dup]).sample(frac=1, random_state=4).reset_index(drop=True)
    return customers, lines


def generate_all(seed: int = config.RANDOM_STATE) -> dict:
    rng = np.random.default_rng(seed)
    products = generate_products(rng)
    customers = generate_customers(rng)
    lines = generate_orders(rng, customers, products)
    customers, lines = inject_quality_issues(rng, customers, lines)
    return {"customers": customers, "products": products, "order_lines": lines}


def save_raw(tables: dict) -> None:
    config.ensure_dirs()
    for name, df in tables.items():
        df.to_csv(config.RAW_DIR / f"{name}.csv", index=False)

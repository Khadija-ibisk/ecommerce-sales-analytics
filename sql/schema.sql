-- Entrepôt de données en étoile (SQLite)
-- 1 table de faits (lignes de commande) + 3 dimensions

DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_customer;
DROP TABLE IF EXISTS dim_product;

CREATE TABLE dim_date (
    date_key     INTEGER PRIMARY KEY,      -- AAAAMMJJ
    full_date    TEXT    NOT NULL,
    year         INTEGER NOT NULL,
    quarter      INTEGER NOT NULL,
    month        INTEGER NOT NULL,
    month_name   TEXT    NOT NULL,
    year_month   TEXT    NOT NULL,
    weekday      INTEGER NOT NULL,         -- 1 = lundi
    is_weekend   INTEGER NOT NULL
);

CREATE TABLE dim_customer (
    customer_id          TEXT PRIMARY KEY,
    gender               TEXT,
    age                  INTEGER,
    age_band             TEXT,
    city                 TEXT,
    region               TEXT,
    acquisition_channel  TEXT
);

CREATE TABLE dim_product (
    product_id    TEXT PRIMARY KEY,
    product_name  TEXT NOT NULL,
    category      TEXT NOT NULL,
    unit_price    REAL NOT NULL,
    unit_cost     REAL NOT NULL
);

CREATE TABLE fact_sales (
    order_id        TEXT    NOT NULL,
    line_number     INTEGER NOT NULL,
    date_key        INTEGER NOT NULL REFERENCES dim_date(date_key),
    customer_id     TEXT    NOT NULL REFERENCES dim_customer(customer_id),
    product_id      TEXT    NOT NULL REFERENCES dim_product(product_id),
    payment_method  TEXT,
    status          TEXT    NOT NULL CHECK (status IN ('Livrée', 'Retournée', 'Annulée')),
    quantity        INTEGER NOT NULL CHECK (quantity > 0),
    unit_price      REAL    NOT NULL,
    discount_pct    INTEGER NOT NULL,
    net_amount      REAL    NOT NULL,
    margin          REAL    NOT NULL,
    PRIMARY KEY (order_id, line_number)
);

CREATE INDEX idx_fact_date     ON fact_sales(date_key);
CREATE INDEX idx_fact_customer ON fact_sales(customer_id);
CREATE INDEX idx_fact_product  ON fact_sales(product_id);

-- Vue des ventes réalisées (hors commandes annulées et retournées)
DROP VIEW IF EXISTS v_sales;
CREATE VIEW v_sales AS
SELECT f.*, d.full_date, d.year, d.month, d.year_month, d.weekday,
       p.category, p.product_name, c.region, c.age_band, c.acquisition_channel
FROM fact_sales f
JOIN dim_date d     ON d.date_key = f.date_key
JOIN dim_product p  ON p.product_id = f.product_id
JOIN dim_customer c ON c.customer_id = f.customer_id
WHERE f.status = 'Livrée';

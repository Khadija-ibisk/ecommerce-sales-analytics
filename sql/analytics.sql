-- Requêtes analytiques exécutées par le pipeline.
-- Chaque requête est identifiée par un commentaire "-- name: <nom>".

-- name: kpis_annuels
SELECT
    year                                            AS annee,
    ROUND(SUM(net_amount), 0)                       AS chiffre_affaires,
    ROUND(SUM(margin), 0)                           AS marge_brute,
    ROUND(100.0 * SUM(margin) / SUM(net_amount), 1) AS taux_marge_pct,
    COUNT(DISTINCT order_id)                        AS nb_commandes,
    COUNT(DISTINCT customer_id)                     AS nb_clients_actifs,
    ROUND(SUM(net_amount) / COUNT(DISTINCT order_id), 2) AS panier_moyen
FROM v_sales
GROUP BY year
ORDER BY year;

-- name: ca_mensuel
SELECT
    year_month                     AS mois,
    ROUND(SUM(net_amount), 2)      AS chiffre_affaires,
    COUNT(DISTINCT order_id)       AS nb_commandes
FROM v_sales
GROUP BY year_month
ORDER BY year_month;

-- name: croissance_categories
SELECT
    category                                                             AS categorie,
    ROUND(SUM(CASE WHEN year = 2023 THEN net_amount ELSE 0 END), 0)      AS ca_2023,
    ROUND(SUM(CASE WHEN year = 2024 THEN net_amount ELSE 0 END), 0)      AS ca_2024,
    ROUND(100.0 * (SUM(CASE WHEN year = 2024 THEN net_amount ELSE 0 END)
                 - SUM(CASE WHEN year = 2023 THEN net_amount ELSE 0 END))
                 / SUM(CASE WHEN year = 2023 THEN net_amount ELSE 0 END), 1) AS croissance_pct,
    ROUND(100.0 * SUM(margin) / SUM(net_amount), 1)                      AS taux_marge_pct
FROM v_sales
GROUP BY category
ORDER BY ca_2024 DESC;

-- name: top_produits_2024
WITH ventes AS (
    SELECT product_name, category, SUM(net_amount) AS ca, SUM(quantity) AS unites
    FROM v_sales
    WHERE year = 2024
    GROUP BY product_name, category
)
SELECT
    RANK() OVER (ORDER BY ca DESC)        AS rang,
    product_name                          AS produit,
    category                              AS categorie,
    unites,
    ROUND(ca, 0)                          AS chiffre_affaires,
    ROUND(100.0 * ca / SUM(ca) OVER (), 2) AS part_ca_pct
FROM ventes
ORDER BY rang
LIMIT 10;

-- name: taux_retour_categories
SELECT
    p.category                                                          AS categorie,
    COUNT(*)                                                            AS nb_lignes,
    ROUND(100.0 * SUM(f.status = 'Retournée') / COUNT(*), 2)            AS taux_retour_pct,
    ROUND(100.0 * SUM(f.status = 'Annulée') / COUNT(*), 2)              AS taux_annulation_pct
FROM fact_sales f
JOIN dim_product p ON p.product_id = f.product_id
GROUP BY p.category
ORDER BY taux_retour_pct DESC;

-- name: ca_par_region
SELECT
    region,
    ROUND(SUM(net_amount), 0)                                       AS chiffre_affaires,
    COUNT(DISTINCT customer_id)                                     AS nb_clients,
    ROUND(SUM(net_amount) / COUNT(DISTINCT customer_id), 2)         AS ca_par_client
FROM v_sales
WHERE year = 2024
GROUP BY region
ORDER BY chiffre_affaires DESC;

-- name: canaux_acquisition
SELECT
    acquisition_channel                                         AS canal,
    COUNT(DISTINCT customer_id)                                 AS nb_clients,
    ROUND(SUM(net_amount) / COUNT(DISTINCT customer_id), 2)     AS valeur_client_moyenne,
    ROUND(1.0 * COUNT(DISTINCT order_id) / COUNT(DISTINCT customer_id), 2) AS commandes_par_client
FROM v_sales
GROUP BY acquisition_channel
ORDER BY valeur_client_moyenne DESC;

-- name: rfm_base
-- Récence / Fréquence / Montant par client, notés de 1 à 5 avec NTILE
WITH clients AS (
    SELECT
        customer_id,
        CAST(julianday('2024-12-31') - julianday(MAX(full_date)) AS INTEGER) AS recence_jours,
        COUNT(DISTINCT order_id)                                             AS frequence,
        ROUND(SUM(net_amount), 2)                                            AS montant
    FROM v_sales
    GROUP BY customer_id
)
SELECT
    customer_id,
    recence_jours,
    frequence,
    montant,
    NTILE(5) OVER (ORDER BY recence_jours DESC) AS score_r,
    NTILE(5) OVER (ORDER BY frequence ASC)      AS score_f,
    NTILE(5) OVER (ORDER BY montant ASC)        AS score_m
FROM clients;

-- name: cohortes
-- Mois de premier achat de chaque client et mois d'activité suivants
WITH premier_achat AS (
    SELECT customer_id, MIN(year_month) AS cohorte
    FROM v_sales
    GROUP BY customer_id
)
SELECT
    p.cohorte,
    s.year_month                         AS mois_activite,
    COUNT(DISTINCT s.customer_id)        AS clients_actifs
FROM v_sales s
JOIN premier_achat p ON p.customer_id = s.customer_id
GROUP BY p.cohorte, s.year_month
ORDER BY p.cohorte, s.year_month;

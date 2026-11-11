"""Configuration centrale du projet."""
from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = ROOT_DIR / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
SQL_DIR = ROOT_DIR / "sql"

DB_FILE = PROCESSED_DIR / "warehouse.db"

RANDOM_STATE = 2025
START_DATE = "2023-01-01"
END_DATE = "2024-12-31"
N_CUSTOMERS = 2500
N_PRODUCTS = 120

# Date d'édition affichée dans les rapports (date de génération)
REPORT_DATE = date.today()

CATEGORIES = {
    # catégorie: (prix moyen, marge brute moyenne)
    "Électronique": (180.0, 0.18),
    "Maison": (65.0, 0.35),
    "Mode": (45.0, 0.50),
    "Beauté": (28.0, 0.55),
    "Sport": (55.0, 0.40),
    "Livres": (18.0, 0.30),
}

REGIONS = {
    "Paris": "Île-de-France",
    "Lyon": "Auvergne-Rhône-Alpes",
    "Marseille": "Provence-Alpes-Côte d'Azur",
    "Toulouse": "Occitanie",
    "Lille": "Hauts-de-France",
    "Bordeaux": "Nouvelle-Aquitaine",
    "Nantes": "Pays de la Loire",
    "Strasbourg": "Grand Est",
    "Rennes": "Bretagne",
    "Nice": "Provence-Alpes-Côte d'Azur",
}

MONTHS_FR = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def ensure_dirs() -> None:
    for d in (RAW_DIR, PROCESSED_DIR, FIGURES_DIR):
        d.mkdir(parents=True, exist_ok=True)


def report_date_fr() -> str:
    d = REPORT_DATE
    months = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
              "septembre", "octobre", "novembre", "décembre"]
    return f"{d.day} {months[d.month - 1]} {d.year}"

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[2]

RAW_DATA_PATH = Path(os.getenv("RAW_DATA_PATH", "data/raw/sales.csv"))
CURATED_DATA_PATH = Path(os.getenv("CURATED_DATA_PATH", "data/curated"))

if not RAW_DATA_PATH.is_absolute():
    RAW_DATA_PATH = BASE_DIR / RAW_DATA_PATH

if not CURATED_DATA_PATH.is_absolute():
    CURATED_DATA_PATH = BASE_DIR / CURATED_DATA_PATH

POSTGRES_DB = os.getenv("POSTGRES_DB", "retail_data")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}",
)

# Fail the run if more than this share of raw rows is rejected by data quality rules.
MAX_REJECTION_RATE = float(os.getenv("MAX_REJECTION_RATE", "0.05"))

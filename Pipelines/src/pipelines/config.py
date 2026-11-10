"""Settings read from environment variables (and an optional .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str) -> List[str]:
    value = os.getenv(name, "")
    return [item.strip().upper() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    # Source API
    api_base_url: str
    base_currency: str
    symbols: List[str]  # empty means "all currencies the API publishes"
    http_timeout_seconds: float
    http_max_retries: int

    # Storage
    data_dir: Path
    database_url: str

    # Alerting
    slack_webhook_url: Optional[str]
    alert_on_retry: bool
    airflow_base_url: str

    @classmethod
    def from_env(cls) -> Settings:
        """Read the environment *now*, so Airflow, Docker and tests can override values."""
        data_dir = Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data")))
        return cls(
            api_base_url=os.getenv("FX_API_BASE_URL", "https://api.frankfurter.dev/v1"),
            base_currency=os.getenv("FX_BASE_CURRENCY", "USD").upper(),
            symbols=_env_list("FX_SYMBOLS"),
            http_timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "10")),
            http_max_retries=int(os.getenv("HTTP_MAX_RETRIES", "3")),
            data_dir=data_dir,
            database_url=os.getenv("DATABASE_URL", f"sqlite:///{data_dir / 'warehouse.db'}"),
            slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL") or None,
            alert_on_retry=_env_bool("ALERT_ON_RETRY", True),
            airflow_base_url=os.getenv("AIRFLOW_BASE_URL", "http://localhost:8080"),
        )

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "landing" / "raw"

    @property
    def clean_dir(self) -> Path:
        return self.data_dir / "landing" / "clean"


def get_settings() -> Settings:
    return Settings.from_env()

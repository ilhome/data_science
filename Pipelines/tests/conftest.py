from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict

import pytest

from pipelines.config import Settings

AS_OF = date(2024, 1, 15)


def make_payload(**overrides: Any) -> Dict[str, Any]:
    payload = {
        "amount": 1.0,
        "base": "USD",
        "date": "2024-01-15",
        "rates": {"EUR": 0.91366, "GBP": 0.78643, "JPY": 145.72},
    }
    payload.update(overrides)
    return payload


def make_envelope(**payload_overrides: Any) -> Dict[str, Any]:
    return {
        "as_of_date": AS_OF.isoformat(),
        "extracted_at": "2024-01-15T06:00:00+00:00",
        "source": "https://example.test/v1",
        "payload": make_payload(**payload_overrides),
    }


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Settings pointing every side effect at a temp directory and a temp SQLite DB."""
    monkeypatch.setenv("FX_API_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("FX_BASE_CURRENCY", "USD")
    monkeypatch.delenv("FX_SYMBOLS", raising=False)
    monkeypatch.setenv("HTTP_MAX_RETRIES", "1")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'warehouse.db'}")
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    return Settings.from_env()


@pytest.fixture
def raw_file(settings: Settings) -> Path:
    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    path = settings.raw_dir / f"{AS_OF.isoformat()}.json"
    path.write_text(json.dumps(make_envelope()))
    return path

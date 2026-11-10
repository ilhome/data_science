"""Transform: reshape the raw API envelope into validated, tidy rows.

Input : one JSON envelope written by :mod:`pipelines.extract`.
Output: a CSV with one row per (as_of_date, base_currency, quote_currency).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from pipelines.config import Settings, get_settings

log = logging.getLogger(__name__)

CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
COLUMNS = ["as_of_date", "rate_date", "base_currency", "quote_currency", "rate", "extracted_at"]


class TransformError(ValueError):
    """The raw data failed validation and must not be loaded."""


def envelope_to_frame(envelope: Dict[str, Any]) -> pd.DataFrame:
    """Unpivot ``{"rates": {"EUR": 0.9, ...}}`` into one row per currency."""
    payload = envelope["payload"]
    rows = [
        {
            "as_of_date": envelope["as_of_date"],
            "rate_date": payload["date"],
            "base_currency": str(payload["base"]).upper(),
            "quote_currency": str(quote).upper(),
            "rate": rate,
            "extracted_at": envelope["extracted_at"],
        }
        for quote, rate in payload["rates"].items()
    ]
    return pd.DataFrame(rows, columns=COLUMNS)


def validate(frame: pd.DataFrame) -> pd.DataFrame:
    """Enforce the contract the warehouse relies on; raise on any violation.

    We fail loudly rather than quarantining, because a partial set of FX rates
    is worse than none: downstream consumers would silently use stale values.
    """
    if frame.empty:
        raise TransformError("No rate rows to transform")

    problems = []

    rates = pd.to_numeric(frame["rate"], errors="coerce")
    if rates.isna().any():
        problems.append(f"{int(rates.isna().sum())} non-numeric rates")
    if (rates <= 0).any():
        problems.append(f"{int((rates <= 0).sum())} non-positive rates")

    for col in ("base_currency", "quote_currency"):
        bad = ~frame[col].astype(str).str.match(CURRENCY_RE)
        if bad.any():
            problems.append(f"{int(bad.sum())} invalid {col} codes")

    for col in ("as_of_date", "rate_date"):
        parsed = pd.to_datetime(frame[col], errors="coerce", format="%Y-%m-%d")
        if parsed.isna().any():
            problems.append(f"{int(parsed.isna().sum())} unparseable {col} values")

    if (frame["base_currency"] == frame["quote_currency"]).any():
        problems.append("base currency appears as its own quote")

    dupes = frame.duplicated(subset=["as_of_date", "base_currency", "quote_currency"]).sum()
    if dupes:
        problems.append(f"{int(dupes)} duplicate currency pairs")

    if problems:
        raise TransformError("Validation failed: " + "; ".join(problems))

    clean = frame.copy()
    clean["rate"] = rates.round(8)
    return clean.sort_values("quote_currency").reset_index(drop=True)


def transform(raw_path: Path, settings: Optional[Settings] = None) -> Path:
    """Read a raw envelope, validate it and write ``data/landing/clean/<date>.csv``."""
    settings = settings or get_settings()
    envelope = json.loads(Path(raw_path).read_text())

    frame = validate(envelope_to_frame(envelope))

    as_of = date.fromisoformat(envelope["as_of_date"])
    settings.clean_dir.mkdir(parents=True, exist_ok=True)
    out_path = settings.clean_dir / f"{as_of.isoformat()}.csv"
    frame.to_csv(out_path, index=False)
    log.info("Wrote %d clean rows to %s", len(frame), out_path)
    return out_path

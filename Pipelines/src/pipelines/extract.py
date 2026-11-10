"""Extract: pull one day of FX rates from the source API into the raw landing zone.

The output file is keyed by the requested date, so re-running the same day
overwrites the same file instead of creating duplicates (idempotent extract).
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from pipelines.config import Settings, get_settings

log = logging.getLogger(__name__)

# Transient failures worth retrying inside the task. Anything else bubbles up
# to Airflow, which applies its own (slower, exponential) retry policy.
RETRYABLE_STATUS = (429, 500, 502, 503, 504)


class ExtractError(RuntimeError):
    """The source returned something we cannot use."""


def build_session(max_retries: int) -> requests.Session:
    retry = Retry(
        total=max_retries,
        backoff_factor=0.5,
        status_forcelist=RETRYABLE_STATUS,
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


def fetch_rates(
    as_of: date, settings: Settings, session: Optional[requests.Session] = None
) -> Dict[str, Any]:
    """Call the API for ``as_of`` and return the parsed JSON payload."""
    session = session or build_session(settings.http_max_retries)
    url = f"{settings.api_base_url.rstrip('/')}/{as_of.isoformat()}"
    params: Dict[str, str] = {"base": settings.base_currency}
    if settings.symbols:
        params["symbols"] = ",".join(settings.symbols)

    log.info("GET %s params=%s", url, params)
    response = session.get(url, params=params, timeout=settings.http_timeout_seconds)
    if response.status_code != 200:
        raise ExtractError(f"{url} returned HTTP {response.status_code}: {response.text[:200]}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise ExtractError(f"{url} returned non-JSON body") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("rates"), dict):
        raise ExtractError(f"Unexpected payload shape from {url}: {str(payload)[:200]}")
    if not payload["rates"]:
        raise ExtractError(f"{url} returned no rates for {as_of}")
    return payload


def extract(as_of: date, settings: Optional[Settings] = None) -> Path:
    """Fetch rates for ``as_of`` and write them to ``data/landing/raw/<date>.json``."""
    settings = settings or get_settings()
    payload = fetch_rates(as_of, settings)

    envelope = {
        "as_of_date": as_of.isoformat(),
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "source": settings.api_base_url,
        "payload": payload,
    }

    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    out_path = settings.raw_dir / f"{as_of.isoformat()}.json"
    out_path.write_text(json.dumps(envelope, indent=2))
    log.info("Wrote %d rates to %s", len(payload["rates"]), out_path)
    return out_path

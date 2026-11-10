"""Load: write clean rows into the warehouse table, idempotently.

Each run replaces the partition ``(as_of_date, base_currency)`` inside a single
transaction: delete the old rows, insert the new ones, commit. Re-running a
day (or backfilling) therefore never produces duplicates, and readers never
observe a half-written partition.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import sqlalchemy as sa
from sqlalchemy.engine import Engine

from pipelines.config import Settings, get_settings

log = logging.getLogger(__name__)

metadata = sa.MetaData()

fx_rates = sa.Table(
    "fx_rates",
    metadata,
    sa.Column("as_of_date", sa.Date, primary_key=True),
    sa.Column("base_currency", sa.String(3), primary_key=True),
    sa.Column("quote_currency", sa.String(3), primary_key=True),
    sa.Column("rate_date", sa.Date, nullable=False),
    sa.Column("rate", sa.Numeric(18, 8), nullable=False),
    sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=False),
)


def get_engine(settings: Optional[Settings] = None) -> Engine:
    settings = settings or get_settings()
    if settings.database_url.startswith("sqlite:///"):
        Path(settings.database_url[len("sqlite:///") :]).parent.mkdir(parents=True, exist_ok=True)
    return sa.create_engine(settings.database_url, future=True)


def ensure_schema(engine: Engine) -> None:
    metadata.create_all(engine, tables=[fx_rates])


def read_clean(clean_path: Path) -> pd.DataFrame:
    frame = pd.read_csv(clean_path, dtype={"base_currency": str, "quote_currency": str})
    frame["as_of_date"] = pd.to_datetime(frame["as_of_date"]).dt.date
    frame["rate_date"] = pd.to_datetime(frame["rate_date"]).dt.date
    frame["extracted_at"] = pd.to_datetime(frame["extracted_at"], utc=True)
    return frame


def load(
    clean_path: Path, settings: Optional[Settings] = None, engine: Optional[Engine] = None
) -> int:
    """Load one clean CSV into ``fx_rates``. Returns the number of rows written."""
    settings = settings or get_settings()
    engine = engine or get_engine(settings)
    ensure_schema(engine)

    frame = read_clean(Path(clean_path))
    if frame.empty:
        raise ValueError(f"{clean_path} is empty; refusing to load nothing")

    partitions = frame[["as_of_date", "base_currency"]].drop_duplicates()
    loaded_at = datetime.now(timezone.utc)
    records = [
        {
            "as_of_date": row.as_of_date,
            "base_currency": row.base_currency,
            "quote_currency": row.quote_currency,
            "rate_date": row.rate_date,
            "rate": row.rate,
            "extracted_at": row.extracted_at.to_pydatetime(),
            "loaded_at": loaded_at,
        }
        for row in frame.itertuples(index=False)
    ]

    with engine.begin() as conn:
        for part in partitions.itertuples(index=False):
            deleted = conn.execute(
                sa.delete(fx_rates).where(
                    fx_rates.c.as_of_date == part.as_of_date,
                    fx_rates.c.base_currency == part.base_currency,
                )
            ).rowcount
            log.info(
                "Replaced partition as_of=%s base=%s (%d old rows)",
                part.as_of_date,
                part.base_currency,
                deleted,
            )
        conn.execute(sa.insert(fx_rates), records)

    log.info("Loaded %d rows into fx_rates", len(records))
    return len(records)


def count_rows(engine: Engine, as_of: date, base_currency: str) -> int:
    with engine.connect() as conn:
        stmt = (
            sa.select(sa.func.count())
            .select_from(fx_rates)
            .where(fx_rates.c.as_of_date == as_of, fx_rates.c.base_currency == base_currency)
        )
        return int(conn.execute(stmt).scalar_one())


def partition_health(engine: Engine, as_of: date, base_currency: str) -> dict:
    """Metrics used by the post-load quality check."""
    with engine.connect() as conn:
        stmt = (
            sa.select(
                sa.func.count().label("rows"),
                sa.func.sum(sa.case((fx_rates.c.rate <= 0, 1), else_=0)).label("non_positive"),
                sa.func.count(sa.distinct(fx_rates.c.quote_currency)).label("distinct_quotes"),
            )
            .select_from(fx_rates)
            .where(fx_rates.c.as_of_date == as_of, fx_rates.c.base_currency == base_currency)
        )
        row = conn.execute(stmt).one()
    return {
        "rows": int(row.rows or 0),
        "non_positive": int(row.non_positive or 0),
        "distinct_quotes": int(row.distinct_quotes or 0),
    }

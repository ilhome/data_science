"""Load curated data into the warehouse's raw layer."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from data_engineering_project.config import DATABASE_URL


def get_engine(url: Optional[str] = None) -> Engine:
    return create_engine(url or DATABASE_URL, pool_pre_ping=True)


def replace_table(
    df: pd.DataFrame, table: str, engine: Engine, schema: Optional[str] = "raw"
) -> int:
    """Atomically replace a table's contents with ``df``.

    Rows are deleted and re-inserted inside a single transaction, so re-running the
    pipeline is idempotent and readers never observe a half-loaded table. The table
    keeps its DDL (see ``sql/init.sql``); it is only created here if missing.
    """
    payload = df.assign(loaded_at=datetime.now(timezone.utc))
    with engine.begin() as conn:
        if schema:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        if inspect(conn).has_table(table, schema=schema):
            qualified = f'"{schema}"."{table}"' if schema else f'"{table}"'
            conn.execute(text(f"DELETE FROM {qualified}"))
        payload.to_sql(
            table,
            conn,
            schema=schema,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=1_000,
        )
    return len(payload)

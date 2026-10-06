from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine

from data_engineering_project.generate import generate_sales, write_csv
from data_engineering_project.pipeline import run_pipeline


@pytest.fixture
def raw_file(tmp_path: Path) -> Path:
    return write_csv(generate_sales(n_orders=300, n_customers=50, seed=7), tmp_path / "sales.csv")


def test_run_pipeline_creates_outputs(raw_file: Path, tmp_path: Path) -> None:
    result = run_pipeline(raw_file, tmp_path / "curated")

    assert result.cleaned_data.exists()
    assert result.rejected_data.exists()
    assert result.daily_metrics.exists()
    assert result.rows_valid > 0
    assert result.rows_rejected > 0  # the generator injects dirty records
    assert result.rows_loaded == 0  # no engine given


def test_run_pipeline_loads_database_idempotently(raw_file: Path, tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'warehouse.db'}")

    for _ in range(2):  # re-running must replace, not duplicate, the data
        result = run_pipeline(raw_file, tmp_path / "curated", engine=engine, db_schema=None)

    loaded = pd.read_sql("select * from sales", engine)
    rejected = pd.read_sql("select * from sales_rejected", engine)
    assert len(loaded) == result.rows_loaded == result.rows_valid
    assert len(rejected) == result.rows_rejected
    assert loaded["loaded_at"].notna().all()


def test_run_pipeline_fails_on_high_rejection_rate(raw_file: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Rejection rate"):
        run_pipeline(raw_file, tmp_path / "curated", max_rejection_rate=0.0)


def test_generator_is_deterministic() -> None:
    assert generate_sales(n_orders=50, seed=1) == generate_sales(n_orders=50, seed=1)

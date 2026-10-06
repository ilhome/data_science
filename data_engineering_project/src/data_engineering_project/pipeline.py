from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from sqlalchemy.engine import Engine

from data_engineering_project.config import CURATED_DATA_PATH, MAX_REJECTION_RATE, RAW_DATA_PATH
from data_engineering_project.etl import (
    build_daily_metrics,
    extract_sales,
    split_sales_records,
    validate_data_quality,
)
from data_engineering_project.load import get_engine, replace_table

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    cleaned_data: Path
    rejected_data: Path
    daily_metrics: Path
    rows_valid: int
    rows_rejected: int
    rows_loaded: int = 0


def run_pipeline(
    raw_path: Union[str, Path] = RAW_DATA_PATH,
    curated_dir: Union[str, Path] = CURATED_DATA_PATH,
    engine: Optional[Engine] = None,
    db_schema: Optional[str] = "raw",
    max_rejection_rate: float = MAX_REJECTION_RATE,
) -> PipelineResult:
    """Run the ETL workflow end-to-end.

    Files are always written to ``curated_dir``. When an ``engine`` is given, the clean
    and rejected records are also loaded into the warehouse for dbt to model.
    """
    raw_path = Path(raw_path)
    curated_dir = Path(curated_dir)
    curated_dir.mkdir(parents=True, exist_ok=True)

    sales_df = extract_sales(raw_path)
    valid_df, rejected_df = split_sales_records(sales_df)
    logger.info(
        "Extracted %d rows from %s: %d valid, %d rejected",
        len(sales_df),
        raw_path,
        len(valid_df),
        len(rejected_df),
    )
    if not rejected_df.empty:
        logger.info(
            "Rejections by reason: %s",
            rejected_df["rejection_reason"].value_counts().to_dict(),
        )
    validate_data_quality(valid_df, rejected_df, max_rejection_rate)

    daily_metrics_df = build_daily_metrics(valid_df)

    result = PipelineResult(
        cleaned_data=curated_dir / "sales_clean.parquet",
        rejected_data=curated_dir / "sales_rejected.csv",
        daily_metrics=curated_dir / "daily_sales_metrics.parquet",
        rows_valid=len(valid_df),
        rows_rejected=len(rejected_df),
    )
    valid_df.to_parquet(result.cleaned_data, index=False)
    rejected_df.to_csv(result.rejected_data, index=False)
    daily_metrics_df.to_parquet(result.daily_metrics, index=False)

    if engine is not None:
        result.rows_loaded = replace_table(valid_df, "sales", engine, schema=db_schema)
        replace_table(rejected_df, "sales_rejected", engine, schema=db_schema)
        logger.info("Loaded %d rows into %s.sales", result.rows_loaded, db_schema)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the retail sales ETL pipeline.")
    parser.add_argument("--raw-path", type=Path, default=RAW_DATA_PATH)
    parser.add_argument("--curated-dir", type=Path, default=CURATED_DATA_PATH)
    parser.add_argument(
        "--load", action="store_true", help="Also load results into PostgreSQL (raw schema)."
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = run_pipeline(
        args.raw_path, args.curated_dir, engine=get_engine() if args.load else None
    )
    logger.info("Cleaned dataset saved to: %s", result.cleaned_data)
    logger.info("Rejected records saved to: %s", result.rejected_data)
    logger.info("Daily metrics saved to: %s", result.daily_metrics)


if __name__ == "__main__":
    main()

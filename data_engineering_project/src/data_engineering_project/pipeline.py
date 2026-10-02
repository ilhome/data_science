from __future__ import annotations

from pathlib import Path
from typing import Dict, Union

from data_engineering_project.config import CURATED_DATA_PATH, RAW_DATA_PATH
from data_engineering_project.etl import (
    build_daily_metrics,
    clean_sales_data,
    extract_sales,
    validate_data_quality,
)


def run_pipeline(raw_path: Union[str, Path] = RAW_DATA_PATH, curated_dir: Union[str, Path] = CURATED_DATA_PATH) -> Dict[str, Path]:
    """Run the ETL workflow end-to-end."""
    raw_path = Path(raw_path)
    curated_dir = Path(curated_dir)
    curated_dir.mkdir(parents=True, exist_ok=True)

    sales_df = extract_sales(raw_path)
    cleaned_df = clean_sales_data(sales_df)
    validate_data_quality(cleaned_df)

    daily_metrics_df = build_daily_metrics(cleaned_df)

    cleaned_output = curated_dir / "sales_clean.csv"
    metrics_output = curated_dir / "daily_sales_metrics.parquet"

    cleaned_df.to_csv(cleaned_output, index=False)
    daily_metrics_df.to_parquet(metrics_output, index=False)

    return {
        "cleaned_data": cleaned_output,
        "daily_metrics": metrics_output,
    }


if __name__ == "__main__":
    outputs = run_pipeline()
    print(f"Cleaned dataset saved to: {outputs['cleaned_data']}")
    print(f"Daily metrics saved to: {outputs['daily_metrics']}")

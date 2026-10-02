from __future__ import annotations

from pathlib import Path
from typing import Union

import pandas as pd

REQUIRED_COLUMNS = {
    "order_id",
    "order_date",
    "customer_id",
    "product",
    "quantity",
    "unit_price",
}


def extract_sales(path: Union[str, Path]) -> pd.DataFrame:
    """Load raw sales data from CSV."""
    data_path = Path(path)
    df = pd.read_csv(data_path)
    missing = sorted(REQUIRED_COLUMNS - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    return df


def clean_sales_data(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize and validate the sales dataset before downstream processing."""
    cleaned = df.copy()
    cleaned["order_id"] = cleaned["order_id"].astype(str).str.strip()
    cleaned["customer_id"] = cleaned["customer_id"].astype(str).str.strip()
    cleaned["product"] = cleaned["product"].astype(str).str.strip()
    cleaned["order_date"] = pd.to_datetime(cleaned["order_date"], errors="coerce")
    cleaned["quantity"] = pd.to_numeric(cleaned["quantity"], errors="coerce").fillna(0).astype(int)
    cleaned["unit_price"] = pd.to_numeric(cleaned["unit_price"], errors="coerce").fillna(0.0)
    cleaned["total_amount"] = (cleaned["quantity"] * cleaned["unit_price"]).round(2)

    cleaned = cleaned.dropna(subset=["order_id", "customer_id", "product", "order_date"]).copy()
    cleaned = cleaned[cleaned["quantity"] > 0].copy()
    cleaned = cleaned[cleaned["unit_price"] >= 0].copy()
    cleaned = cleaned.sort_values("order_date").reset_index(drop=True)
    return cleaned


def build_daily_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate metrics by day for BI and reporting layers."""
    daily = (
        df.assign(order_date=lambda frame: frame["order_date"].dt.normalize())
        .groupby("order_date", as_index=False)
        .agg(
            total_orders=("order_id", "nunique"),
            total_revenue=("total_amount", "sum"),
            total_units=("quantity", "sum"),
        )
        .sort_values("order_date")
        .reset_index(drop=True)
    )
    daily["total_revenue"] = daily["total_revenue"].round(2)
    return daily


def validate_data_quality(df: pd.DataFrame) -> None:
    """Fail fast when the cleaned dataset is empty or invalid."""
    if df.empty:
        raise ValueError("No valid rows remained after cleaning.")
    if df["total_amount"].lt(0).any():
        raise ValueError("Negative revenue values detected.")

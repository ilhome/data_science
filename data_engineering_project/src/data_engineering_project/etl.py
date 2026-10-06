from __future__ import annotations

from pathlib import Path
from typing import Tuple, Union

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = {
    "order_id",
    "order_date",
    "customer_id",
    "product",
    "quantity",
    "unit_price",
}
TEXT_COLUMNS = ["order_id", "customer_id", "product"]
# A single order can contain each product at most once.
LINE_KEY = ["order_id", "product"]


def extract_sales(path: Union[str, Path]) -> pd.DataFrame:
    """Load raw sales data from CSV, keeping every value as text like a landing zone."""
    data_path = Path(path)
    df = pd.read_csv(data_path, dtype=str, keep_default_na=False)
    missing = sorted(REQUIRED_COLUMNS - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    return df


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    for column in TEXT_COLUMNS:
        normalized[column] = normalized[column].astype("string").str.strip().replace("", pd.NA)
    normalized["order_date"] = pd.to_datetime(
        normalized["order_date"], format="%Y-%m-%d", errors="coerce"
    )
    normalized["quantity"] = pd.to_numeric(normalized["quantity"], errors="coerce")
    normalized["unit_price"] = pd.to_numeric(normalized["unit_price"], errors="coerce")
    return normalized


def split_sales_records(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split raw records into (valid, rejected).

    Rejected rows keep their original raw values plus a ``rejection_reason`` so they
    can be quarantined and inspected instead of silently disappearing.
    """
    normalized = _normalize(df)
    quantity = normalized["quantity"]
    checks = [
        (normalized["order_id"].isna(), "missing_order_id"),
        (normalized["customer_id"].isna(), "missing_customer_id"),
        (normalized["product"].isna(), "missing_product"),
        (normalized["order_date"].isna(), "invalid_order_date"),
        (quantity.isna() | (quantity <= 0) | (quantity % 1 != 0), "invalid_quantity"),
        (normalized["unit_price"].isna() | (normalized["unit_price"] < 0), "invalid_unit_price"),
    ]
    reasons = pd.Series(
        np.select(
            [mask.fillna(True).to_numpy(bool) for mask, _ in checks],
            [reason for _, reason in checks],
            default="",
        ),
        index=df.index,
    )
    # Only rows that passed every other rule compete for the "first copy" slot.
    passed = reasons.eq("")
    duplicated = normalized[passed].duplicated(subset=LINE_KEY, keep="first")
    reasons[duplicated[duplicated].index] = "duplicate_record"

    is_valid = reasons.eq("")
    valid = normalized[is_valid].copy()
    valid["quantity"] = valid["quantity"].astype(int)
    valid["unit_price"] = valid["unit_price"].round(2)
    valid["total_amount"] = (valid["quantity"] * valid["unit_price"]).round(2)
    for column in TEXT_COLUMNS:
        valid[column] = valid[column].astype(str)
    valid = valid.sort_values(["order_date", "order_id", "product"]).reset_index(drop=True)

    rejected = df[~is_valid].astype(str).assign(rejection_reason=reasons[~is_valid])
    return valid, rejected.reset_index(drop=True)


def clean_sales_data(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize and validate the sales dataset before downstream processing."""
    valid, _ = split_sales_records(df)
    return valid


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


def validate_data_quality(
    valid: pd.DataFrame, rejected: pd.DataFrame, max_rejection_rate: float = 1.0
) -> None:
    """Fail fast when the cleaned dataset is empty, inconsistent, or too much was rejected."""
    if valid.empty:
        raise ValueError("No valid rows remained after cleaning.")
    if valid["total_amount"].lt(0).any():
        raise ValueError("Negative revenue values detected.")
    if valid.duplicated(subset=LINE_KEY).any():
        raise ValueError(f"Duplicate order lines detected on {LINE_KEY}.")
    if valid[sorted(REQUIRED_COLUMNS)].isna().any().any():
        raise ValueError("Null values detected in required columns.")

    rejection_rate = len(rejected) / (len(valid) + len(rejected))
    if rejection_rate > max_rejection_rate:
        raise ValueError(
            f"Rejection rate {rejection_rate:.1%} exceeds threshold {max_rejection_rate:.1%}."
        )

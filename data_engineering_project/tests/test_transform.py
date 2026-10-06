from __future__ import annotations

import pandas as pd
import pytest
from conftest import make_row

from data_engineering_project.etl import (
    build_daily_metrics,
    clean_sales_data,
    split_sales_records,
    validate_data_quality,
)


def test_clean_sales_data_removes_invalid_rows() -> None:
    sales = pd.DataFrame(
        [
            make_row(order_id="A-100", quantity=2, unit_price=1200),
            make_row(order_id="A-101", product="Mouse", quantity=0, unit_price=50),
            make_row(order_id="A-102", order_date="bad-date", product="Keyboard"),
        ]
    )

    cleaned = clean_sales_data(sales)

    assert len(cleaned) == 1
    assert cleaned["total_amount"].iloc[0] == 2400.0
    assert cleaned["order_date"].notna().all()


@pytest.mark.parametrize(
    "overrides, reason",
    [
        ({"order_id": ""}, "missing_order_id"),
        ({"customer_id": "   "}, "missing_customer_id"),
        ({"product": ""}, "missing_product"),
        ({"order_date": "2024-13-45"}, "invalid_order_date"),
        ({"order_date": "not-a-date"}, "invalid_order_date"),
        ({"quantity": "0"}, "invalid_quantity"),
        ({"quantity": "-1"}, "invalid_quantity"),
        ({"quantity": "1.5"}, "invalid_quantity"),
        ({"quantity": "abc"}, "invalid_quantity"),
        ({"unit_price": "N/A"}, "invalid_unit_price"),
        ({"unit_price": "-5"}, "invalid_unit_price"),
    ],
)
def test_split_sales_records_tags_rejection_reason(overrides, reason) -> None:
    valid, rejected = split_sales_records(pd.DataFrame([make_row(**overrides)]))

    assert valid.empty
    assert rejected["rejection_reason"].tolist() == [reason]


def test_rejected_rows_keep_original_raw_values() -> None:
    _, rejected = split_sales_records(pd.DataFrame([make_row(unit_price="N/A")]))

    assert rejected["unit_price"].iloc[0] == "N/A"


def test_duplicates_are_rejected_and_first_copy_kept() -> None:
    sales = pd.DataFrame([make_row(), make_row(), make_row(product="  Laptop ")])

    valid, rejected = split_sales_records(sales)

    assert len(valid) == 1
    assert rejected["rejection_reason"].tolist() == ["duplicate_record", "duplicate_record"]


def test_invalid_first_copy_does_not_shadow_valid_duplicate() -> None:
    sales = pd.DataFrame([make_row(unit_price="N/A"), make_row()])

    valid, rejected = split_sales_records(sales)

    assert len(valid) == 1
    assert rejected["rejection_reason"].tolist() == ["invalid_unit_price"]


def test_strings_are_trimmed(raw_sales: pd.DataFrame) -> None:
    raw_sales.loc[0, "product"] = "  Laptop "

    valid, _ = split_sales_records(raw_sales)

    assert "Laptop" in valid["product"].tolist()


def test_validate_data_quality_enforces_rejection_threshold(raw_sales: pd.DataFrame) -> None:
    raw_sales.loc[0, "quantity"] = "0"
    valid, rejected = split_sales_records(raw_sales)

    validate_data_quality(valid, rejected, max_rejection_rate=0.5)
    with pytest.raises(ValueError, match="Rejection rate"):
        validate_data_quality(valid, rejected, max_rejection_rate=0.1)


def test_validate_data_quality_rejects_empty_dataset() -> None:
    valid, rejected = split_sales_records(pd.DataFrame([make_row(quantity="0")]))

    with pytest.raises(ValueError, match="No valid rows"):
        validate_data_quality(valid, rejected)


def test_build_daily_metrics_aggregates_revenue(raw_sales: pd.DataFrame) -> None:
    raw_sales.loc[1, "order_id"] = "A-100"  # two lines in the same order

    metrics = build_daily_metrics(clean_sales_data(raw_sales))

    assert metrics["total_orders"].tolist() == [1, 1]
    assert metrics["total_revenue"].tolist() == [2475.0, 300.0]
    assert metrics["total_units"].tolist() == [5, 1]

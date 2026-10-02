from __future__ import annotations

import pandas as pd

from data_engineering_project.etl import build_daily_metrics, clean_sales_data


def test_clean_sales_data_removes_invalid_rows() -> None:
    sales = pd.DataFrame(
        [
            {
                "order_id": "A-100",
                "order_date": "2024-01-01",
                "customer_id": "C1",
                "product": "Laptop",
                "quantity": 2,
                "unit_price": 1200,
            },
            {
                "order_id": "A-101",
                "order_date": "2024-01-01",
                "customer_id": "C2",
                "product": "Mouse",
                "quantity": 0,
                "unit_price": 50,
            },
            {
                "order_id": "A-102",
                "order_date": "bad-date",
                "customer_id": "C3",
                "product": "Keyboard",
                "quantity": 1,
                "unit_price": 80,
            },
        ]
    )

    cleaned = clean_sales_data(sales)

    assert len(cleaned) == 1
    assert cleaned["total_amount"].iloc[0] == 2400.0
    assert cleaned["order_date"].notna().all()


def test_build_daily_metrics_aggregates_revenue() -> None:
    sales = pd.DataFrame(
        [
            {
                "order_id": "A-100",
                "order_date": pd.Timestamp("2024-01-01"),
                "customer_id": "C1",
                "product": "Laptop",
                "quantity": 1,
                "unit_price": 1000,
                "total_amount": 1000.0,
            },
            {
                "order_id": "A-101",
                "order_date": pd.Timestamp("2024-01-01"),
                "customer_id": "C2",
                "product": "Mouse",
                "quantity": 2,
                "unit_price": 25,
                "total_amount": 50.0,
            },
            {
                "order_id": "A-102",
                "order_date": pd.Timestamp("2024-01-02"),
                "customer_id": "C1",
                "product": "Monitor",
                "quantity": 1,
                "unit_price": 300,
                "total_amount": 300.0,
            },
        ]
    )

    metrics = build_daily_metrics(sales)

    assert metrics["total_orders"].tolist() == [2, 1]
    assert metrics["total_revenue"].tolist() == [1050.0, 300.0]

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import pytest


def make_row(**overrides: Any) -> Dict[str, Any]:
    row = {
        "order_id": "A-100",
        "order_date": "2024-01-01",
        "customer_id": "C1",
        "product": "Laptop",
        "quantity": "2",
        "unit_price": "1200",
    }
    row.update(overrides)
    return row


@pytest.fixture
def raw_sales() -> pd.DataFrame:
    rows: List[Dict[str, Any]] = [
        make_row(),
        make_row(order_id="A-101", product="Mouse", quantity="3", unit_price="25"),
        make_row(
            order_id="A-102",
            order_date="2024-01-02",
            product="Monitor",
            quantity="1",
            unit_price="300",
        ),
    ]
    return pd.DataFrame(rows)

"""Generate a realistic, reproducible raw sales dataset.

The output mimics an export from a point-of-sale system: one row per order line,
with seasonality, repeat customers, discounts, and a small share of dirty records
(blank ids, malformed dates, bad quantities/prices, padded strings, duplicates)
that the ETL layer has to handle.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Union

import numpy as np

from data_engineering_project.config import BASE_DIR, RAW_DATA_PATH

CATALOG_PATH = BASE_DIR / "dbt" / "seeds" / "product_catalog.csv"
FIELDS = ["order_id", "order_date", "customer_id", "product", "quantity", "unit_price"]

# Monthly demand multipliers (Jan..Dec): quiet summer, strong Q4 holiday season.
MONTH_WEIGHTS = [0.85, 0.8, 0.9, 0.9, 0.95, 0.85, 0.8, 0.95, 1.0, 1.05, 1.4, 1.6]
WEEKDAY_WEIGHTS = [0.9, 0.9, 0.95, 1.0, 1.15, 1.3, 1.1]
QUANTITIES, QUANTITY_WEIGHTS = [1, 2, 3, 4, 5], [0.6, 0.2, 0.1, 0.06, 0.04]


def load_catalog(path: Path = CATALOG_PATH) -> List[Dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _order_dates(rng: np.random.Generator, start: date, end: date, n_orders: int) -> List[date]:
    days = [start + timedelta(days=offset) for offset in range((end - start).days + 1)]
    weights = np.array([MONTH_WEIGHTS[d.month - 1] * WEEKDAY_WEIGHTS[d.weekday()] for d in days])
    picks = rng.choice(len(days), size=n_orders, p=weights / weights.sum())
    return sorted(days[i] for i in picks)


def generate_sales(
    n_orders: int = 20_000,
    n_customers: int = 1_500,
    start: date = date(2024, 1, 1),
    end: date = date(2024, 12, 31),
    dirty_rate: float = 0.02,
    seed: int = 42,
) -> List[Dict[str, str]]:
    """Return raw order-line records as strings, exactly as they would land in CSV."""
    rng = np.random.default_rng(seed)
    catalog = load_catalog()
    # Cheap accessories sell far more often than laptops.
    popularity = np.array([1 / float(item["list_price"]) ** 0.5 for item in catalog])
    popularity /= popularity.sum()
    # A long tail of customers: a few loyal buyers, many one-off shoppers.
    customer_weights = rng.pareto(1.2, n_customers) + 1
    customer_weights /= customer_weights.sum()

    rows: List[Dict[str, str]] = []
    for number, order_date in enumerate(_order_dates(rng, start, end, n_orders), start=1):
        customer = f"C{rng.choice(n_customers, p=customer_weights) + 1:05d}"
        n_lines = int(rng.choice([1, 2, 3], p=[0.6, 0.3, 0.1]))
        for idx in rng.choice(len(catalog), size=n_lines, replace=False, p=popularity):
            item = catalog[idx]
            discount = rng.choice([1.0, 0.95, 0.9, 0.8], p=[0.7, 0.15, 0.1, 0.05])
            rows.append(
                {
                    "order_id": f"ORD-{number:06d}",
                    "order_date": order_date.isoformat(),
                    "customer_id": customer,
                    "product": item["product_name"],
                    "quantity": str(int(rng.choice(QUANTITIES, p=QUANTITY_WEIGHTS))),
                    "unit_price": f"{float(item['list_price']) * discount:.2f}",
                }
            )

    return _inject_dirty_records(rows, rng, dirty_rate)


def _inject_dirty_records(
    rows: List[Dict[str, str]], rng: np.random.Generator, dirty_rate: float
) -> List[Dict[str, str]]:
    corruptions = [
        ("customer_id", lambda value: ""),
        ("order_date", lambda value: "2024-13-45"),
        ("order_date", lambda value: "not-a-date"),
        ("quantity", lambda value: "0"),
        ("quantity", lambda value: "-1"),
        ("unit_price", lambda value: "N/A"),
        ("product", lambda value: f"  {value} "),  # recoverable: trimmed by the ETL
    ]
    n_dirty = int(len(rows) * dirty_rate)
    for row_idx in rng.choice(len(rows), size=n_dirty, replace=False):
        column, corrupt = corruptions[rng.integers(len(corruptions))]
        rows[row_idx][column] = corrupt(rows[row_idx][column])

    # Upstream re-sends: exact duplicate lines scattered through the file.
    for row_idx in rng.choice(len(rows), size=max(1, n_dirty // 2), replace=False):
        rows.append(dict(rows[row_idx]))
    return rows


def write_csv(rows: List[Dict[str, str]], path: Union[str, Path]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--orders", type=int, default=20_000)
    parser.add_argument("--customers", type=int, default=1_500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=RAW_DATA_PATH)
    args = parser.parse_args()

    rows = generate_sales(n_orders=args.orders, n_customers=args.customers, seed=args.seed)
    path = write_csv(rows, args.output)
    print(f"Wrote {len(rows):,} rows to {path}")


if __name__ == "__main__":
    main()

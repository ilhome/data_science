"""Run the ETL steps in sequence without Airflow (handy for local dev and CI).

python -m pipelines.run --date 2024-01-15
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timezone

from pipelines import extract, load, quality, transform
from pipelines.config import get_settings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the FX rates ETL for one day.")
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        default=datetime.now(timezone.utc).date(),
        help="Logical date (YYYY-MM-DD). Defaults to today (UTC).",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    raw_path = extract.extract(args.date)
    clean_path = transform.transform(raw_path)
    rows = load.load(clean_path)

    settings = get_settings()
    quality.check_partition(load.get_engine(settings), args.date, settings.base_currency, rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())

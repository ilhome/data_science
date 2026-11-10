"""Post-load quality gate: verify what actually landed in the warehouse.

Shared by the Airflow task and the standalone runner so both enforce the same rules.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Dict, List

from sqlalchemy.engine import Engine

from pipelines.load import partition_health

log = logging.getLogger(__name__)


class QualityCheckError(RuntimeError):
    """The loaded partition violates the contract. Not transient: do not retry."""


def find_problems(health: Dict[str, int], expected_rows: int) -> List[str]:
    problems = []
    if health["rows"] == 0:
        problems.append("no rows landed")
    if health["rows"] != expected_rows:
        problems.append(f"expected {expected_rows} rows, found {health['rows']}")
    if health["non_positive"]:
        problems.append(f"{health['non_positive']} non-positive rates")
    if health["distinct_quotes"] != health["rows"]:
        problems.append("duplicate quote currencies")
    return problems


def check_partition(engine: Engine, as_of: date, base_currency: str, expected_rows: int) -> Dict:
    """Raise :class:`QualityCheckError` unless the partition is complete and sane."""
    health = partition_health(engine, as_of, base_currency)
    log.info("Partition health for %s/%s: %s", as_of, base_currency, health)
    problems = find_problems(health, expected_rows)
    if problems:
        raise QualityCheckError(f"Quality check failed for {as_of}: " + "; ".join(problems))
    return health

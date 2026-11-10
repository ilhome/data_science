"""### FX rates pipeline

Daily extract → transform → load of foreign-exchange reference rates.

* **extract** – pulls the day's rates from the public API into `data/landing/raw/`
* **transform** – validates and reshapes them into `data/landing/clean/`
* **load** – replaces that day's partition in the `fx_rates` warehouse table
* **quality_check** – verifies what landed; fails the run (no retries) on bad data

Every task is keyed by the run's logical date, so the DAG is safe to re-run
and to backfill. Failures retry with exponential backoff and alert to Slack.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from airflow.exceptions import AirflowFailException
from airflow.sdk import dag, get_current_context, task

from pipelines import alerts

default_args = {
    "owner": "data-platform",
    # Retry policy: 1 min, 2 min, 4 min (capped at max_retry_delay).
    "retries": 3,
    "retry_delay": timedelta(minutes=1),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=15),
    # A hung HTTP call or DB lock should fail (and retry), not block the slot.
    "execution_timeout": timedelta(minutes=10),
    # Alerts: on every retry, and once when retries are exhausted.
    "on_retry_callback": alerts.on_retry_callback,
    "on_failure_callback": alerts.on_failure_callback,
}


def _logical_date() -> date:
    ctx = get_current_context()
    return date.fromisoformat(ctx["ds"])


@dag(
    dag_id="fx_rates_pipeline",
    description="Daily FX rates ETL with retries, data quality gate and Slack alerts.",
    schedule="0 6 * * *",  # 06:00 UTC, after the ECB publishes the previous day's fixing
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    on_success_callback=alerts.on_dag_success_callback,
    doc_md=__doc__,
    tags=["fx", "etl", "daily"],
)
def fx_rates_pipeline():
    @task
    def extract() -> str:
        from pipelines.extract import extract as run_extract

        return str(run_extract(_logical_date()))

    @task
    def transform(raw_path: str) -> str:
        from pipelines.transform import transform as run_transform

        return str(run_transform(raw_path))

    @task
    def load(clean_path: str) -> int:
        from pipelines.load import load as run_load

        return run_load(clean_path)

    @task(retries=0)
    def quality_check(expected_rows: int) -> None:
        """Bad data is not transient, so this task fails immediately without retrying."""
        from pipelines.config import get_settings
        from pipelines.load import get_engine
        from pipelines.quality import QualityCheckError, check_partition

        settings = get_settings()
        try:
            check_partition(
                get_engine(settings), _logical_date(), settings.base_currency, expected_rows
            )
        except QualityCheckError as exc:
            raise AirflowFailException(str(exc)) from exc

    raw_path = extract()
    clean_path = transform(raw_path)
    rows = load(clean_path)
    quality_check(rows)


fx_rates_pipeline()

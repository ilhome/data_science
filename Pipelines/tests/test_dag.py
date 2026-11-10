"""DAG integrity tests. Skipped when Airflow is not installed (unit-test only envs)."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

pytest.importorskip("airflow.sdk", reason="Airflow is only installed in the Airflow image / CI")

from airflow.models import DagBag  # noqa: E402
from pipelines import alerts  # noqa: E402

DAGS_DIR = Path(__file__).resolve().parents[1] / "airflow" / "dags"


@pytest.fixture(scope="module")
def dag():
    dag_bag = DagBag(dag_folder=str(DAGS_DIR), include_examples=False)
    assert dag_bag.import_errors == {}
    # .dags is the parsed result; get_dag() would also consult the metadata DB.
    assert "fx_rates_pipeline" in dag_bag.dags
    return dag_bag.dags["fx_rates_pipeline"]


def test_task_order(dag):
    assert [t.task_id for t in dag.topological_sort()] == [
        "extract",
        "transform",
        "load",
        "quality_check",
    ]
    assert dag.get_task("transform").upstream_task_ids == {"extract"}
    assert dag.get_task("load").upstream_task_ids == {"transform"}
    assert dag.get_task("quality_check").upstream_task_ids == {"load"}


def test_retry_policy_on_etl_tasks(dag):
    for task_id in ("extract", "transform", "load"):
        task = dag.get_task(task_id)
        assert task.retries == 3, task_id
        assert task.retry_delay == timedelta(minutes=1), task_id
        assert task.retry_exponential_backoff is True, task_id
        assert task.max_retry_delay == timedelta(minutes=15), task_id
        assert task.execution_timeout == timedelta(minutes=10), task_id


def test_quality_check_never_retries(dag):
    assert dag.get_task("quality_check").retries == 0


def test_alert_callbacks_are_wired(dag):
    for task in dag.tasks:
        assert alerts.on_failure_callback in _as_list(task.on_failure_callback), task.task_id
        assert alerts.on_retry_callback in _as_list(task.on_retry_callback), task.task_id
    assert alerts.on_dag_success_callback in _as_list(dag.on_success_callback)


def test_schedule_guards(dag):
    assert dag.catchup is False
    assert dag.max_active_runs == 1
    assert dag.timetable.summary == "0 6 * * *"


def _as_list(value):
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]

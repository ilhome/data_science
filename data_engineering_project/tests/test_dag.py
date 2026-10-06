from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("airflow.sdk", reason="Airflow is only installed in the Airflow image")

from airflow.models import DagBag  # noqa: E402

DAGS_DIR = Path(__file__).resolve().parents[1] / "airflow" / "dags"


def test_dag_loads_without_errors() -> None:
    dag_bag = DagBag(dag_folder=str(DAGS_DIR), include_examples=False)

    assert dag_bag.import_errors == {}
    dag = dag_bag.get_dag("retail_sales_pipeline")
    assert dag is not None
    assert [task.task_id for task in dag.topological_sort()] == [
        "extract_validate_load",
        "dbt_source_freshness",
        "dbt_build",
    ]

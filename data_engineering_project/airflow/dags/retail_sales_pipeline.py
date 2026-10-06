"""Daily retail sales pipeline: Python ETL into the raw layer, then dbt models and tests.

The ETL and dbt run in a dedicated virtualenv baked into the image
(``/opt/pipeline_venv``) so their dependencies never conflict with Airflow's own.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

PROJECT_DIR = "/opt/project"
VENV_BIN = "/opt/pipeline_venv/bin"
DBT = f"{VENV_BIN}/dbt --no-use-colors"
DBT_ARGS = f"--project-dir {PROJECT_DIR}/dbt --profiles-dir {PROJECT_DIR}/dbt"

with DAG(
    dag_id="retail_sales_pipeline",
    description="Extract, validate and load retail sales, then build the dbt warehouse.",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["retail", "etl", "dbt"],
) as dag:
    extract_validate_load = BashOperator(
        task_id="extract_validate_load",
        bash_command=f"{VENV_BIN}/python -m data_engineering_project.pipeline --load",
        cwd=PROJECT_DIR,
        env={"PYTHONPATH": f"{PROJECT_DIR}/src"},
        append_env=True,
    )

    source_freshness = BashOperator(
        task_id="dbt_source_freshness",
        bash_command=f"{DBT} source freshness {DBT_ARGS}",
    )

    # `dbt build` runs seeds, models and tests in dependency order and stops
    # downstream models when an upstream test fails.
    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=f"{DBT} build {DBT_ARGS}",
    )

    extract_validate_load >> source_freshness >> dbt_build

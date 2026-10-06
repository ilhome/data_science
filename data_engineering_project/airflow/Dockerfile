FROM apache/airflow:3.0.6-python3.11

# Pipeline code + dbt live in their own virtualenv, isolated from Airflow's packages.
USER root
RUN mkdir -p /opt/pipeline_venv && chown airflow: /opt/pipeline_venv
USER airflow

COPY requirements.txt /tmp/requirements.txt
RUN python -m venv /opt/pipeline_venv \
    && /opt/pipeline_venv/bin/pip install --no-cache-dir \
        -r /tmp/requirements.txt "dbt-core>=1.10,<2.0" "dbt-postgres>=1.9,<2.0"

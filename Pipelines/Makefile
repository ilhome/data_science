.PHONY: help setup setup-airflow run test test-dag dag-test lint format up down logs clean

VENV := .venv
PYTHON := $(VENV)/bin/python
AIRFLOW_VERSION := 3.0.6
PY_MINOR := $(shell $(PYTHON) -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
CONSTRAINTS := https://raw.githubusercontent.com/apache/airflow/constraints-$(AIRFLOW_VERSION)/constraints-$(PY_MINOR).txt
DATE ?= $(shell date -u +%Y-%m-%d)

export AIRFLOW_HOME := $(CURDIR)/airflow_home
export AIRFLOW__CORE__DAGS_FOLDER := $(CURDIR)/airflow/dags
export AIRFLOW__CORE__LOAD_EXAMPLES := False
export PYTHONPATH := $(CURDIR)/src

help:  ## Show available targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

setup:  ## Create the virtualenv with the pipeline + dev tools (no Airflow)
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements-dev.txt
	$(VENV)/bin/pip install -e .

setup-airflow: setup  ## Also install Airflow locally, for `make dag-test` without Docker
	$(VENV)/bin/pip install "apache-airflow==$(AIRFLOW_VERSION)" apache-airflow-providers-standard \
		--constraint "$(CONSTRAINTS)"

run:  ## Run extract → transform → load → quality check for DATE without Airflow
	$(PYTHON) -m pipelines.run --date $(DATE)

test:  ## Unit tests (DAG tests auto-skip unless Airflow is installed)
	$(PYTHON) -m pytest -q

dag-test:  ## Execute the whole DAG for DATE through Airflow's task runner
	$(VENV)/bin/airflow db migrate
	$(VENV)/bin/airflow dags test fx_rates_pipeline $(DATE)

lint:  ## Check lint and formatting
	$(VENV)/bin/ruff check src tests airflow
	$(VENV)/bin/ruff format --check src tests airflow

format:  ## Auto-format and fix lint issues
	$(VENV)/bin/ruff format src tests airflow
	$(VENV)/bin/ruff check --fix src tests airflow

up:  ## Start Postgres + Airflow (UI on http://localhost:8080)
	docker compose up -d --build

down:  ## Stop the stack and delete its volumes
	docker compose down -v

logs:  ## Tail Airflow logs
	docker compose logs -f airflow

clean:  ## Remove generated outputs and local Airflow state
	rm -rf data/landing/raw/*.json data/landing/clean/*.csv data/*.db airflow_home logs .pytest_cache .ruff_cache

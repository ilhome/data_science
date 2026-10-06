.PHONY: help setup data up down run load dbt-build dbt-docs airflow-up test lint format all clean

VENV := .venv
PYTHON := $(VENV)/bin/python
DBT := $(VENV)/bin/dbt --no-use-colors
DBT_ARGS := --project-dir dbt --profiles-dir dbt

# Make the .env settings visible to dbt and the pipeline.
-include .env
export

help:  ## Show available targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

setup:  ## Create the virtualenv and install the project with dev tools
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements-dev.txt
	$(VENV)/bin/pip install -e .

data:  ## Regenerate the synthetic raw sales dataset
	$(PYTHON) -m data_engineering_project.generate

up:  ## Start Postgres, pgAdmin and Airflow
	docker compose up -d --build

down:  ## Stop the stack and delete its volumes
	docker compose down -v

run:  ## Run the ETL and write curated files only
	$(PYTHON) -m data_engineering_project.pipeline

load:  ## Run the ETL and load the raw layer in Postgres
	$(PYTHON) -m data_engineering_project.pipeline --load

dbt-build:  ## Build and test all dbt models
	$(DBT) build $(DBT_ARGS)

dbt-docs:  ## Generate and serve dbt docs with lineage graph
	$(DBT) docs generate $(DBT_ARGS) && $(DBT) docs serve $(DBT_ARGS) --port 8081

all: load dbt-build  ## Full local run: ETL + load + dbt

test:  ## Run unit tests
	$(PYTHON) -m pytest -q

lint:  ## Check lint and formatting
	$(VENV)/bin/ruff check src tests airflow
	$(VENV)/bin/ruff format --check src tests airflow

format:  ## Auto-format and fix lint issues
	$(VENV)/bin/ruff format src tests airflow
	$(VENV)/bin/ruff check --fix src tests airflow

clean:  ## Remove generated outputs
	rm -rf data/curated/*.parquet data/curated/*.csv dbt/target dbt/logs logs .pytest_cache

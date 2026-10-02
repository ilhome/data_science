# Data Engineering Project Starter

A production-style data engineering starter project built around a realistic retail analytics workflow.

## What this project includes

- Python-based ETL pipeline
- Sample raw sales dataset
- Data cleaning and transformation logic
- Quality checks and unit tests
- PostgreSQL + pgAdmin via Docker Compose
- Simple warehouse-ready outputs in parquet format
- Makefile for quick local execution

## Project architecture

- `src/data_engineering_project/etl.py` – extraction, transformation, validation
- `src/data_engineering_project/pipeline.py` – orchestration entry point
- `src/data_engineering_project/config.py` – environment settings
- `data/raw/` – raw landing data
- `data/curated/` – cleaned output tables
- `sql/init.sql` – database initialization script
- `tests/` – validation tests

## Quick start

1. Copy the environment template:
   ```bash
   cp .env.example .env
   ```

2. Start the database stack:
   ```bash
   make up
   ```

3. Run the pipeline:
   ```bash
   make run
   ```

4. Run the test suite:
   ```bash
   make test
   ```

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
```

## Default stack

- Python 3.9+
- pandas
- SQLAlchemy
- psycopg2-binary
- pyarrow
- pytest
- Docker Compose with PostgreSQL and pgAdmin

## Example workload

The pipeline ingests sample retail sales data, cleans invalid records, normalizes dates and currency values, and produces daily revenue metrics ready for a warehouse or BI layer.

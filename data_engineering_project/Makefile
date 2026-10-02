.PHONY: setup up down run test lint

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

setup:
	python3 -m venv $(VENV)
	$(PIP) install -r requirements.txt
	$(PIP) install -e .

up:
	docker compose up -d

down:
	docker compose down -v

run:
	$(PYTHON) -m data_engineering_project.pipeline

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m black src tests
	$(PYTHON) -m ruff check src tests

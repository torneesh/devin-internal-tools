PYTHON ?= python3.11
VENV := .venv
BIN := $(VENV)/bin

.PHONY: setup run test lint fmt

setup:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -q --upgrade pip
	$(BIN)/pip install -q -r requirements.txt

# Fresh database + seed data on every start (the mock payment provider is in-memory too).
run:
	rm -f app.db
	$(BIN)/uvicorn app:create_app --factory --reload --port 8000

test:
	$(BIN)/pytest

lint:
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

fmt:
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

PYTHON ?= python3.11
VENV := .venv
BIN := $(VENV)/bin

.PHONY: setup run test lint fmt sso run-sso

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

# Real SSO demo: Keycloak (OIDC) on :8080, users alice..admin, password "demo".
sso:
	docker compose up -d keycloak
	@echo "Waiting for Keycloak..."; until curl -sf http://localhost:8080/realms/internal-tools/.well-known/openid-configuration >/dev/null; do sleep 2; done; echo ready

run-sso:
	rm -f app.db
	OIDC_ISSUER=http://localhost:8080/realms/internal-tools OIDC_CLIENT_ID=internal-tools \
	OIDC_CLIENT_SECRET=dev-only-client-secret $(BIN)/uvicorn app:create_app --factory --reload --port 8000

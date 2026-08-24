# HELIX developer tasks.
#
# Everything works without a GROQ_API_KEY: the deterministic parser takes over
# whenever the LLM is unavailable.

VENV    ?= .venv
PY      := $(VENV)/bin/python
PIP     := $(VENV)/bin/pip
BACKEND := backend
FRONT   := frontend
PORT    ?= 8000

.DEFAULT_GOAL := help
.PHONY: help setup backend frontend dev test lint fmt smoke build clean docker docker-down reset-db

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Create the virtualenv and install backend + frontend dependencies
	python3 -m venv $(VENV)
	$(PIP) install -q -r $(BACKEND)/requirements-dev.txt
	cd $(FRONT) && npm install --no-audit --no-fund
	@echo "Ready. Run 'make dev' to start both services."

backend: ## Run the API with reload on http://localhost:$(PORT)
	cd $(BACKEND) && ../$(PY) -m uvicorn main:app --reload --port $(PORT)

frontend: ## Run the dashboard on http://localhost:5173
	cd $(FRONT) && npm run dev

dev: ## Run the API and dashboard together
	@$(MAKE) -j2 backend frontend

test: ## Run the backend test suite
	cd $(BACKEND) && ../$(PY) -m pytest

lint: ## Lint the backend and typecheck the frontend
	cd $(BACKEND) && ../$(VENV)/bin/ruff check .
	cd $(FRONT) && npx tsc --noEmit

fmt: ## Apply ruff autofixes to the backend
	cd $(BACKEND) && ../$(VENV)/bin/ruff check --fix .

smoke: ## Run the end-to-end smoke test against a running API
	$(PY) scripts/smoke_test.py --base-url http://localhost:$(PORT)

build: ## Build the production dashboard bundle
	cd $(FRONT) && npm run build

docker: ## Start both services with docker compose
	docker compose up --build

docker-down: ## Stop the docker compose stack
	docker compose down

reset-db: ## Delete the local SQLite database
	rm -f $(BACKEND)/data/helix.db $(BACKEND)/data/helix.db-wal $(BACKEND)/data/helix.db-shm
	@echo "Database cleared; demo slices will be reseeded on next start."

backup-db: ## Take a consistent live backup of the local database
	$(PY) scripts/backup_db.py backup

restore-db: ## Restore the local database: make restore-db FROM=path/to/backup.db
	$(PY) scripts/backup_db.py restore --from $(FROM) --force

verify-db: ## Check the local database's integrity and schema version
	$(PY) scripts/backup_db.py verify $(BACKEND)/data/helix.db

clean: ## Remove build artefacts and caches
	rm -rf $(FRONT)/dist $(FRONT)/node_modules/.vite
	find $(BACKEND) -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf $(BACKEND)/.pytest_cache $(BACKEND)/.ruff_cache

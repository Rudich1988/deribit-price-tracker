# Common commands. Run `make` or `make help` to list them.
#
# Secrets are never written here: recipes that need credentials read them
# from .env at run time (LOAD_ENV), the same file docker compose uses.

.DEFAULT_GOAL := help

COMPOSE := docker compose
POETRY := poetry run
SERVICE ?= app
NAME ?=

# Exports every variable from .env into the recipe's shell.
LOAD_ENV := set -a && . ./.env && set +a
# Postgres from docker compose, as seen from the host (published port).
HOST_DB_URL = postgresql+asyncpg://$${POSTGRES_USER}:$${POSTGRES_PASSWORD}@localhost:$${POSTGRES_HOST_PORT:-5433}
TEST_DB_NAME := prices_test

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# --- Setup -------------------------------------------------------------------

.PHONY: install
install: ## Install dependencies (incl. dev) with Poetry
	poetry install

.PHONY: env
env: ## Create .env from .env.example if it does not exist
	@test -f .env && echo ".env already exists" || (cp .env.example .env && echo "Created .env, now set real passwords in it")

# --- Code quality ------------------------------------------------------------

.PHONY: lint
lint: ## Check code style (ruff check + format check)
	$(POETRY) ruff check .
	$(POETRY) ruff format --check .

.PHONY: format
format: ## Fix lint issues and format the code
	$(POETRY) ruff check --fix .
	$(POETRY) ruff format .

# --- Tests -------------------------------------------------------------------

.PHONY: test
test: ## Run tests without a database (DB tests are skipped)
	$(POETRY) pytest

.PHONY: test-db
test-db: test-db-create ## Run all tests, incl. DB tests against Postgres in docker
	@$(LOAD_ENV) && TEST_DATABASE_URL="$(HOST_DB_URL)/$(TEST_DB_NAME)" $(POETRY) pytest

.PHONY: test-db-create
test-db-create: ## Create the test database in docker Postgres (once)
	@$(LOAD_ENV) && $(COMPOSE) exec -T db psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -tAc \
		"SELECT 1 FROM pg_database WHERE datname = '$(TEST_DB_NAME)'" | grep -q 1 \
		|| $(COMPOSE) exec -T db psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -c "CREATE DATABASE $(TEST_DB_NAME)"

.PHONY: check
check: lint test ## Lint and run tests (what to run before a commit)

# --- Docker ------------------------------------------------------------------

.PHONY: up
up: ## Build and start all services, wait until they are healthy
	$(COMPOSE) up -d --build --wait

.PHONY: down
down: ## Stop all services (data is kept)
	$(COMPOSE) down

.PHONY: down-volumes
down-volumes: ## Stop all services and DELETE the database volume
	$(COMPOSE) down -v

.PHONY: restart
restart: down up ## Restart all services

.PHONY: ps
ps: ## Show service status and health
	$(COMPOSE) ps -a

.PHONY: logs
logs: ## Follow logs of one service: make logs SERVICE=worker (default: app)
	$(COMPOSE) logs -f $(SERVICE)

.PHONY: logs-all
logs-all: ## Follow logs of all services
	$(COMPOSE) logs -f

.PHONY: shell
shell: ## Open a shell in a running service: make shell SERVICE=worker
	$(COMPOSE) exec $(SERVICE) sh

.PHONY: psql
psql: ## Open psql in the docker database
	@$(LOAD_ENV) && $(COMPOSE) exec db psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"

# --- Migrations --------------------------------------------------------------

.PHONY: migrate
migrate: ## Apply migrations to the docker database
	$(COMPOSE) run --rm migrate

.PHONY: migration
migration: ## Create a migration from model changes: make migration NAME="add column"
	@test -n "$(NAME)" || (echo 'Usage: make migration NAME="describe change"' && exit 1)
	@$(LOAD_ENV) && DATABASE_URL="$(HOST_DB_URL)/$${POSTGRES_DB}" $(POETRY) alembic revision --autogenerate -m "$(NAME)"

.PHONY: migration-check
migration-check: ## Check that models and the database schema are in sync
	@$(LOAD_ENV) && DATABASE_URL="$(HOST_DB_URL)/$${POSTGRES_DB}" $(POETRY) alembic check

# --- Run locally (outside docker, db and redis from docker) ------------------

.PHONY: run-api
run-api: ## Run the API locally with reload on :8000 (stop the app container first)
	@$(LOAD_ENV) && DATABASE_URL="$(HOST_DB_URL)/$${POSTGRES_DB}" $(POETRY) uvicorn deribit_price_tracker.app:create_app --factory --reload

# --- Housekeeping ------------------------------------------------------------

.PHONY: clean
clean: ## Remove Python and tool caches
	find . -type d -name __pycache__ -not -path "./.venv/*" -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache

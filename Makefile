# Common commands. Run `make` or `make help` to list them.
#
# The main commands work through Docker only: start the project with
# `make up`, then check it with `make test` and `make lint`, which run
# inside the running app container.
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
TEST_DB_NAME := prices_test
# Test database inside the compose network (used by `make test`).
DOCKER_TEST_DB_URL = postgresql+asyncpg://$${POSTGRES_USER}:$${POSTGRES_PASSWORD}@db:5432/$(TEST_DB_NAME)
# Postgres from docker compose, as seen from the host (published port).
HOST_DB_URL = postgresql+asyncpg://$${POSTGRES_USER}:$${POSTGRES_PASSWORD}@localhost:$${POSTGRES_HOST_PORT:-5433}

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# --- Run in Docker -----------------------------------------------------------

.PHONY: env
env: ## Create .env from .env.example if it does not exist
	@test -f .env && echo ".env already exists" || (cp .env.example .env && echo "Created .env from .env.example")

.PHONY: up
up: ## Build and start the project (migrations are applied on start)
	$(COMPOSE) up -d --build --wait

.PHONY: down
down: ## Stop the project (data is kept)
	$(COMPOSE) down

.PHONY: down-volumes
down-volumes: ## Stop the project and DELETE the database volume
	$(COMPOSE) down -v

.PHONY: restart
restart: down up ## Restart the project

.PHONY: ps
ps: ## Show containers and their status
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
psql: ## Open psql in the database
	@$(LOAD_ENV) && $(COMPOSE) exec db psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"

.PHONY: migrate
migrate: ## Apply migrations (also done automatically by `make up`)
	$(COMPOSE) run --rm migrate

.PHONY: migration-check
migration-check: ## Check that models and the database schema are in sync
	$(COMPOSE) exec -T app alembic check

# --- Check in Docker (the project must be running: `make up`) ---------------

.PHONY: test
test: test-db-create ## Run all tests in the app container, incl. DB tests
	@$(LOAD_ENV) && $(COMPOSE) exec -T -e TEST_DATABASE_URL="$(DOCKER_TEST_DB_URL)" app \
		pytest -p no:cacheprovider

.PHONY: lint
lint: ## Run the linter in the app container (ruff check + format check)
	$(COMPOSE) exec -T app ruff check --no-cache .
	$(COMPOSE) exec -T app ruff format --check --no-cache .

.PHONY: check
check: lint test ## Linter and all tests

.PHONY: test-db-create
test-db-create:
	@$(LOAD_ENV) && $(COMPOSE) exec -T db psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -tAc \
		"SELECT 1 FROM pg_database WHERE datname = '$(TEST_DB_NAME)'" | grep -q 1 \
		|| $(COMPOSE) exec -T db psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -c "CREATE DATABASE $(TEST_DB_NAME)"

# --- Local development (Python 3.12 + Poetry) -------------------------------

.PHONY: install
install: ## [local] Install dependencies with Poetry
	poetry install

.PHONY: test-local
test-local: ## [local] Run tests without a database (DB tests are skipped)
	$(POETRY) pytest

.PHONY: lint-local
lint-local: ## [local] Run the linter
	$(POETRY) ruff check .
	$(POETRY) ruff format --check .

.PHONY: format
format: ## [local] Fix lint issues and format the code
	$(POETRY) ruff check --fix .
	$(POETRY) ruff format .

.PHONY: migration
migration: ## [local] Create a migration: make migration NAME="add column"
	@test -n "$(NAME)" || (echo 'Usage: make migration NAME="describe change"' && exit 1)
	@$(LOAD_ENV) && DATABASE_URL="$(HOST_DB_URL)/$${POSTGRES_DB}" $(POETRY) alembic revision --autogenerate -m "$(NAME)"

.PHONY: run-api
run-api: ## [local] Run the API with reload on :8000 (stop the app container first)
	@$(LOAD_ENV) && DATABASE_URL="$(HOST_DB_URL)/$${POSTGRES_DB}" $(POETRY) uvicorn deribit_price_tracker.app:create_app --factory --reload

.PHONY: clean
clean: ## [local] Remove Python and tool caches
	find . -type d -name __pycache__ -not -path "./.venv/*" -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache

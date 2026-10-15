# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Early-stage scaffold of a Deribit price tracker: a FastAPI service that will fetch index prices from the Deribit API (aiohttp), store them in PostgreSQL (async SQLAlchemy + asyncpg, Alembic migrations), and run periodic fetching through Celery with Redis as the broker. Right now only the app factory, config and DB layer exist. There are no models, routes, Celery tasks, Alembic setup or tests yet.

## Commands

Dependencies are managed with Poetry (Python >= 3.12, src layout, venv in `.venv/`).

```bash
poetry install                                   # install runtime + dev deps
poetry run uvicorn deribit_price_tracker.app:create_app --factory --reload   # run API
poetry run pytest                                # run all tests
poetry run pytest tests/test_x.py::test_name     # run a single test
poetry run ruff check .                          # lint (add --fix to autofix)
poetry run ruff format .                         # format
```

Ruff is configured in `pyproject.toml` with a **max line length of 80** and rule sets E, W, F, I (import sorting), B, UP.

## Configuration

`Config.from_env()` (`config/base.py`) calls `load_dotenv()` and reads `.env` (template: `.env.example`). `DATABASE_URL` is required and must use the `postgresql+asyncpg://` driver. `REDIS_URL` and `DERIBIT_BASE_URL` have defaults. `DEBUG` (`1`/`true`/`yes`, default false) becomes `Config.debug` and is passed as `echo` to `Database`, which turns on SQL logging. `LOG_LEVEL` (default `INFO`) sets the root log level in `setup_logging()` (`core/logging.py`), which `create_app()` calls first. The default hostnames (`db`, `redis`) assume Docker Compose service names. No compose file exists yet, so for local runs point them at `localhost`.

## Architecture

The code follows DDD with strictly separated layers (router → service → repository, dataclass DTOs between them), one package per domain in `src/deribit_price_tracker/<domain>/`. The rules are in the `ddd-architecture` skill. The `new-domain` skill scaffolds a domain or endpoint. No module-level variables or constants (absence of globals is an evaluation criterion of the task); see the `ddd-architecture` skill.

- `app.py`: `create_app()` is a factory. It builds `Config` and, in the FastAPI lifespan, creates one `Database` and stores it on `app.state.database`. It disposes the engine on shutdown. Endpoints get it through `DatabaseDep` (`db/dependencies.py`), not through `Request`, and never create new engines.
- `db/database.py`: `Database` wraps the async engine and session factory. `database.session()` is an async context manager that **commits on success and rolls back on exception**, so callers must not commit themselves. `expire_on_commit=False` keeps loaded objects usable after the commit.
- `db/base.py`: `ModelBase` is the declarative base. All ORM models should inherit from it, and future Alembic `env.py` should use `ModelBase.metadata` as `target_metadata`.
- Errors: raise subclasses of `AppError` (`core/exceptions.py`) from services and clients, never `HTTPException`. `AppErrorHandler` (`core/handlers.py`) maps them to HTTP codes via its `_status_codes`. Add new mappings there. Unmapped `AppError`s and any other exception become a generic 500 with the traceback logged (`UnhandledErrorMiddleware`). `RequestLoggingMiddleware` is added last, so it is outermost and logs the final status.
- Tests use `fastapi.testclient.TestClient` (needs `httpx2`, not `httpx`). Build the app through `create_app()` with `DATABASE_URL` set via `monkeypatch`. The lifespan does not run without `with TestClient(...)`, so no database is needed. pytest-asyncio is available for async tests.

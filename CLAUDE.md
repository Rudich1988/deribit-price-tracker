# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Early-stage scaffold of a Deribit price tracker: a FastAPI service that will fetch index prices from the Deribit API (aiohttp), store them in PostgreSQL (async SQLAlchemy + asyncpg, Alembic migrations), and run periodic fetching through Celery with Redis as the broker. Right now only the app factory, config and DB layer exist. There are no models, routes, Celery tasks, Alembic setup or tests yet.

## Commands

Dependencies are managed with Poetry (Python >= 3.12, src layout, venv in `.venv/`).

```bash
poetry install                                   # install runtime + dev deps
poetry run uvicorn deribit_price_tracker.app:create_app --factory --reload   # run API
poetry run python -m deribit_price_tracker.worker worker --beat --loglevel INFO  # Celery worker + beat
poetry run pytest                                # run all tests
poetry run pytest tests/test_x.py::test_name     # run a single test
poetry run ruff check .                          # lint (add --fix to autofix)
poetry run ruff format .                         # format
```

Docker (`Dockerfile` + `docker-compose.yml`, secrets only from `.env`):

```bash
docker compose up -d --build --wait              # db, redis, migrate, app on :8000, worker
docker compose logs -f app
docker compose down                              # add -v to drop the database volume
```

Compose runs a one-shot `migrate` service (`alembic upgrade head`) before `app` starts. app, migrate and worker share the image `deribit-price-tracker:latest`, built only by `app`. Every long-running service has a healthcheck: app polls `GET /health` (python urllib, there is no curl in the slim image), worker runs `inspect ping` against itself. `--wait` blocks until all are healthy. `/health` is excluded from request logging, and uvicorn runs with `--no-access-log`, because `RequestLoggingMiddleware` already logs every request.

Migrations (async Alembic, `migrations/`). `env.py` reads `DATABASE_URL` from `Config`, never from `alembic.ini`. From the host, point it at the published port:

```bash
export DATABASE_URL=postgresql+asyncpg://<user>:<password>@localhost:5433/prices
poetry run alembic revision --autogenerate -m "describe change"   # ruff runs on the new file
poetry run alembic upgrade head
poetry run alembic check                         # models and DB schema in sync?
```

Every new model module must be imported in `migrations/env.py`, or autogenerate won't see it.

Repository tests need a real Postgres and are **skipped** unless `TEST_DATABASE_URL` is set. They create tables with `metadata.create_all` and truncate them, so use the separate `prices_test` database, never the main one:

```bash
docker compose exec db psql -U <user> -d prices -c "CREATE DATABASE prices_test"   # once
TEST_DATABASE_URL=postgresql+asyncpg://<user>:<password>@localhost:5433/prices_test poetry run pytest
```

Postgres is also published on `127.0.0.1:${POSTGRES_HOST_PORT:-5433}` for running migrations and DB tests from the host. Port 5432 is taken by a local Postgres. In `.env` the `DATABASE_URL` host is `db` (the compose service). From the host, use `localhost:5433` instead.

Ruff is configured in `pyproject.toml` with a **max line length of 80** and rule sets E, W, F, I (import sorting), B, UP.

## Configuration

`Config.from_env()` (`config/base.py`) calls `load_dotenv()` and reads `.env` (template: `.env.example`). `DATABASE_URL` is required and must use the `postgresql+asyncpg://` driver. `REDIS_URL` (Celery broker) and `DERIBIT_BASE_URL` have defaults. `FETCH_INTERVAL_SECONDS` (default 60) is the beat interval. `DEBUG` (`1`/`true`/`yes`, default false) becomes `Config.debug` and is passed as `echo` to `Database`, which turns on SQL logging. `LOG_LEVEL` (default `INFO`) sets the root log level in `setup_logging()` (`core/logging.py`), which `create_app()` calls first. The default hostnames (`db`, `redis`) are the Docker Compose service names.

## Architecture

The code follows DDD with strictly separated layers (router → service → repository, dataclass DTOs between them), one package per domain in `src/deribit_price_tracker/<domain>/`. The rules are in the `ddd-architecture` skill. The `new-domain` skill scaffolds a domain or endpoint. No module-level variables or constants (absence of globals is an evaluation criterion of the task); see the `ddd-architecture` skill.

- `app.py`: `create_app()` is a factory. It builds `Config` and, in the FastAPI lifespan, creates one `Database` and stores it on `app.state.database`. It disposes the engine on shutdown. Endpoints get it through `DatabaseDep` (`db/dependencies.py`), not through `Request`, and never create new engines.
- `db/database.py`: `Database` wraps the async engine and session factory. `database.session()` is an async context manager that **commits on success and rolls back on exception**, so callers must not commit themselves. `expire_on_commit=False` keeps loaded objects usable after the commit.
- `db/base.py`: `ModelBase` is the declarative base. All ORM models should inherit from it, and future Alembic `env.py` should use `ModelBase.metadata` as `target_metadata`.
- Errors: raise subclasses of `AppError` (`core/exceptions.py`) from services and clients, never `HTTPException`. `AppErrorHandler` (`core/handlers.py`) maps them to HTTP codes via its `_status_codes`. Add new mappings there. Unmapped `AppError`s and any other exception become a generic 500 with the traceback logged (`UnhandledErrorMiddleware`). `RequestLoggingMiddleware` is added last, so it is outermost and logs the final status.
- `core/http_client.py`: `BaseHTTPClient` is the base for external API clients (subclass it, call `self._get_json(path, params)`). Use it as `async with`: it owns one `ClientSession` with connection pool limits, timeouts and retries (tenacity, only on `ExternalServiceUnavailableError`: network errors, timeouts, 429/502/503/504). It raises only our `AppError` subclasses, never aiohttp errors, and parses JSON floats as `Decimal`. Override `_raise_for_status(status, payload)` to decode API-specific error bodies. Settings come from `HTTPClientConfig` (`config/http_client.py`), available as `Config.http_client` (`HTTP_TIMEOUT`, `HTTP_CONNECT_TIMEOUT`, `HTTP_RETRY_ATTEMPTS`).
- `prices` domain storage: `Price` model (`ticker`, `price` Numeric(20,8), `timestamp` BigInteger UNIX seconds, index on `(ticker, timestamp)`). `PriceRepository` has `add_one`, `get_all`, `get_latest` (None if empty) and `get_by_period(PricePeriodDTO)`, where the period is half-open `start <= timestamp < end`. `PriceService` raises `NotFoundError` when there is no latest price. `ModelBase.metadata` has a naming convention, so constraint names are stable in migrations.
- Celery: `create_celery_app(config)` (`celery_app.py`) is a factory. `celery -A` cannot call factories and needs a module-level `Celery` instance (a global), so the CLI goes through `python -m deribit_price_tracker.worker <celery args>`, which builds the app and calls `app.start(argv)`. Tasks are registered by job classes, e.g. `IndexPriceCollectionJob.register(app)` (`prices/tasks.py`). Register a closure, never a bound method: Celery reads the signature from the function and would require `self`. Each run does `asyncio.run`, so it creates and disposes its own `Database` and HTTP client. Beat schedule entries set `expires` equal to the interval, so stale runs are dropped. Broker URL and interval come from `CeleryConfig` (`config/celery.py`, `Config.celery`).
- `PriceCollectionService(source, repository).collect(tickers)` fetches all tickers concurrently. A failed ticker is logged (AppError without traceback, anything else with one) and the others are still saved. `PriceSource` is a `Protocol`, so tests pass a fake instead of `DeribitClient`.
- API (`prices/routers.py`, included in `create_app()`): `GET /prices`, `GET /prices/latest` and `GET /prices/by-date`, each with a required `ticker: Ticker` query param (an unknown ticker gives 422). Lists return `200 []` when empty, only `/latest` returns 404. `/by-date` takes `PriceDateFilterQuery` (a pydantic query model): `date_from` / `date_to` are YYYY-MM-DD, UTC, inclusive and optional, and `date_from > date_to` gives 422. `PriceService.get_by_dates` turns them into the half-open `PricePeriodDTO` (bounds may be None). `PriceResponse.price` is serialized as a JSON number, while code uses Decimal internally.
- `prices/clients.py`: `DeribitClient.get_index_price(ticker)` calls `GET public/get_index_price?index_name=...` and returns `IndexPriceDTO`. Its `timestamp` is the exchange time `usOut // 1_000_000`, with local time as fallback. Deribit returns errors as a JSON-RPC `error` body with HTTP 400. Code `10028` (too_many_requests) is retried, other codes are not. `Ticker` (`prices/dto.py`) is the `StrEnum` of tracked indexes.
- API tests (`tests/prices/test_price_routers.py`) use `httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app))` (the package is `httpx2`, not `httpx`). They override `app.dependency_overrides[get_database]`: a stub for validation-only tests, the `database` fixture for tests with data. `TestClient` is used in `tests/core`. Build the app through `create_app()` with `DATABASE_URL` set via `monkeypatch`. The lifespan does not run without `with TestClient(...)`, so no database is needed. pytest runs with `asyncio_mode = "auto"`, so async tests need no marker. HTTP clients are tested against a real local server: fixtures `fake_api` / `fake_api_url` / `http_config` in `tests/conftest.py`, with scripted `FakeResponse`s from `tests/fakes.py`. Override `_retry_wait()` to return `wait_none()` in tests. Shared fakes (`FakeAPI`, `FakeResponse`, `FakePriceRepository`) live in `tests/fakes.py`. DB fixtures (`test_database_url`, `database`) are in `tests/prices/conftest.py`. aioresponses is not used because it is incompatible with aiohttp 3.14.

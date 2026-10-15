---
name: new-domain
description: Scaffolds a new domain package or adds a new endpoint to an existing domain, following the project's layered DDD architecture. Use when asked to create a domain, feature, endpoint or CRUD for an entity. Триггеры: новый домен, новый эндпоинт, добавить ручку, сделать CRUD.
argument-hint: <domain-name>
---

# Create a domain or endpoint

Domain: `$ARGUMENTS`. If it is empty, infer the name from the request
(lowercase, plural, e.g. `prices`) or ask.

1. Read the `ddd-architecture` skill first and follow it for every file.
2. Create `src/deribit_price_tracker/<domain>/` with an empty `__init__.py`
   if it does not exist. Do not overwrite existing files. Extend them.
3. Write the layers bottom-up, in this order:
   1. `models.py`: ORM model inheriting `ModelBase`.
   2. `dto.py`: input and output dataclasses.
   3. `repositories.py`: subclass of `SQLAlchemyRepository` with `model`,
      the needed methods, and `_to_dto`.
   4. `clients.py` (only if an external API is involved): subclass of
      `BaseHTTPClient`.
   5. `services.py`: service taking the repository (and client) in
      `__init__`.
   6. `schemas.py`: pydantic request/response models.
   7. `routers.py`: `router = APIRouter(prefix="/<domain>", tags=[...])`
      and endpoints using `DatabaseDep`.
4. For a new domain, register the router in `create_app()`
   (`src/deribit_price_tracker/app.py`) with `app.include_router(...)`.
5. If a model was added or changed, tell the user a database migration is
   needed. Alembic is a dependency but is not set up yet.
6. Verify:
   ```bash
   poetry run ruff check . && poetry run ruff format --check .
   poetry run python -c "from deribit_price_tracker.app import create_app"
   poetry run pytest
   ```
   The import check needs `DATABASE_URL` in `.env` or the environment.

---
name: ddd-architecture
description: Layered DDD architecture rules for this project (router → service → repository, DTO dataclasses, pydantic schemas, ORM models). Use whenever writing, changing or reviewing code in a domain package — endpoints, services, repositories, DTOs, schemas or models. Триггеры: эндпоинт, роутер, сервис, репозиторий, домен, бизнес-логика, dto, схема, модель.
---

# DDD layered architecture

The project follows DDD with three strictly separated layers:
**router → service → repository**. Layers talk to each other only through
dataclass DTOs. Never mix layers.

## Domain layout

Each domain is a package `src/deribit_price_tracker/<domain>/`:

| File              | Contents                                           |
|-------------------|----------------------------------------------------|
| `routers.py`      | FastAPI `APIRouter` and endpoints                  |
| `schemas.py`      | Pydantic request/response models                   |
| `dto.py`          | `@dataclass` DTOs shared between layers            |
| `services.py`     | Business logic                                     |
| `repositories.py` | Database access                                    |
| `clients.py`      | External API clients (e.g. Deribit, aiohttp)       |
| `models.py`       | SQLAlchemy ORM models (inherit `ModelBase`)        |

## Layer rules

### Router (`routers.py`)
Keep endpoints minimal: no business logic, no queries. The flow is always:
1. Accept a pydantic schema and convert it to a DTO right away:
   `data = PriceCreateDTO(**body.model_dump())`.
2. If the database is needed, take `database: DatabaseDep`
   (`deribit_price_tracker.db.dependencies`) and open a session with
   `async with database.session() as session:`. Never take `Request` just to
   reach `app.state.database`.
3. Build the repository with the session, then the service with the
   repository: `service = PriceService(PriceRepository(session))`.
4. Call the service method. It returns a DTO.
5. Return a pydantic schema built from the DTO:
   `return PriceResponse(**asdict(result))`.

### Service (`services.py`)
- Holds business logic only.
- Receives the repository (and API clients, if any) in `__init__` and knows
  nothing else about storage or transport.
- Accepts a DTO (preferred) or a dict and returns a DTO.
- Never imports `fastapi`, `pydantic`, `sqlalchemy`, `aiohttp`, ORM models
  or `Database`.

### Repository (`repositories.py`)
- Database access only, no business rules.
- Inherits `SQLAlchemyRepository` (`deribit_price_tracker.utils.repository`),
  sets `model`, and implements the abstract methods (`add_one`, …). Keep
  those methods abstract in the base classes. Implement them only here.
- Accepts a DTO (preferred) or a dict and returns a DTO. Never returns ORM
  objects or rows.
- Converts query results through one dedicated method,
  `_to_dto(self, obj) -> DTO`.
- Never calls `commit()`. `Database.session()` commits on exit and rolls
  back on error. Use `flush()` when generated values (ids) are needed.

### DTOs (`dto.py`)
- Plain `@dataclass`, `frozen=True` where it fits. Use separate input and
  output DTOs when their fields differ (e.g. no `id` before insert).
- The only data format crossing layer boundaries.

### External API clients (`clients.py`)
- One class per external API (e.g. `DeribitClient`). It is infrastructure,
  like a repository: it only talks to the API and returns DTOs.
- Receives an `aiohttp.ClientSession` and the base URL (from `Config`) in
  `__init__`. Never creates a session per request. One session is reused for
  the whole lifecycle: the app lifespan, or one Celery task run (a session is
  bound to its event loop, and each task run gets a new loop).
- Endpoint paths and similar service values are class attributes of the
  client.

### Schemas (`schemas.py`) and models (`models.py`)
- Schemas are used only in routers.
- ORM models inherit `ModelBase` (`deribit_price_tracker.db.base`) and are
  used only in repositories.

## No global state

Absence of global variables is an evaluation criterion of the task. Be strict.
- No module-level variables **or constants**. Engines, sessions,
  `ClientSession`, `Config()`, `FastAPI()`, `Database()`, `Celery()`, caches
  and counters are never created at import time.
- Objects are built in factories (`create_app()`) and the lifespan, then
  passed through `__init__` or FastAPI dependencies (`DatabaseDep`).
- Fixed sets of values are enums in `dto.py`, e.g.
  `class Ticker(StrEnum)`. An enum is a type, not a variable, and it also
  validates the `ticker` query parameter.
- Settings (URLs, intervals, timeouts) come from `Config` (env).
- Service values live as class attributes of the class that needs them.
- Loggers are class attributes too: `_logger = logging.getLogger(__name__)`
  in the class body, never a module-level `logger`. Logging is configured
  once by `setup_logging(config)` (`core/logging.py`).
- Allowed at module level: declarations only — classes, functions, enums,
  ORM models, `router = APIRouter(...)`.
- The Celery app is built by a factory as well. The way it is exposed to
  the `celery` CLI is decided at implementation time and explained in the
  README "Design decisions" section.

## Import rules

| Layer        | May import                                         |
|--------------|----------------------------------------------------|
| routers      | schemas, dto, services, repositories, `DatabaseDep` |
| services     | dto, repositories, clients (for type hints)        |
| repositories | dto, models, `SQLAlchemyRepository`, sqlalchemy    |
| clients      | dto, aiohttp                                       |
| schemas      | pydantic, enums from dto                           |
| dto          | stdlib only                                        |
| models       | `ModelBase`, sqlalchemy                            |

## Example

For a full endpoint traced through every layer, see
[reference/example.md](reference/example.md).

## Checklist before finishing

- [ ] No `fastapi` / `pydantic` / `sqlalchemy` imports in `services.py`.
- [ ] ORM models are not used outside `repositories.py` and `models.py`.
- [ ] Repository methods return DTOs built via `_to_dto`.
- [ ] No `commit()` in repositories.
- [ ] Endpoints use `DatabaseDep`, not `Request`.
- [ ] No module-level variables or constants (declarations only).
- [ ] `aiohttp.ClientSession` is created once and passed into the client.
- [ ] Lines ≤ 80 chars: `poetry run ruff check . && poetry run ruff format .`

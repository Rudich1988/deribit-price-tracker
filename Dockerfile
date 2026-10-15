# Build stage: install dependencies with Poetry into an in-project venv.
FROM python:3.12-slim AS builder

ENV POETRY_VERSION=2.4.2 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    PIP_NO_CACHE_DIR=1

RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

# Dependencies first, so this layer is cached until the lock file changes.
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root

COPY src ./src
RUN poetry install --only main


# Runtime stage: only the venv and the code, no Poetry, non-root user.
FROM python:3.12-slim

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN useradd --create-home --uid 1000 app

WORKDIR /app

COPY --from=builder /app/.venv ./.venv
COPY src ./src

USER app

EXPOSE 8000

CMD ["uvicorn", "deribit_price_tracker.app:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000"]

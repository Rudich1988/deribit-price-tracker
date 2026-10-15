import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from deribit_price_tracker.app import create_app
from deribit_price_tracker.core.exceptions import (
    AppError,
    ExternalServiceError,
    ExternalServiceUnavailableError,
    NotFoundError,
)


class UnmappedError(AppError):
    pass


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    app = create_app()

    @app.get("/raise/{kind}")
    async def raise_error(kind: str) -> None:
        errors = {
            "not-found": NotFoundError("Price not found"),
            "unavailable": ExternalServiceUnavailableError("Deribit is down"),
            "external": ExternalServiceError("Bad response"),
            "unmapped": UnmappedError("secret details"),
            "unexpected": RuntimeError("boom"),
        }
        raise errors[kind]

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.mark.parametrize(
    ("kind", "status", "detail"),
    [
        ("not-found", 404, "Price not found"),
        ("unavailable", 503, "Deribit is down"),
        ("external", 502, "Bad response"),
    ],
)
def test_domain_error_is_mapped_to_http_status(
    client: TestClient, kind: str, status: int, detail: str
) -> None:
    response = client.get(f"/raise/{kind}")

    assert response.status_code == status
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize("kind", ["unmapped", "unexpected"])
def test_unexpected_error_returns_500_without_details(
    client: TestClient, caplog: pytest.LogCaptureFixture, kind: str
) -> None:
    response = client.get(f"/raise/{kind}")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal Server Error"}
    assert any(record.exc_info for record in caplog.records)


def test_request_is_logged_with_method_path_and_status(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    client.get("/raise/unexpected")

    messages = [record.getMessage() for record in caplog.records]
    assert any(m.startswith("GET /raise/unexpected 500 ") for m in messages)


def test_framework_http_errors_are_untouched(client: TestClient) -> None:
    response = client.get("/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}

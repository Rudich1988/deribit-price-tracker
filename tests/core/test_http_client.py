import logging
import socket
from decimal import Decimal

import pytest
from tenacity import wait_none
from tenacity.wait import wait_base

from deribit_price_tracker.config.http_client import HTTPClientConfig
from deribit_price_tracker.core.exceptions import (
    ExternalServiceError,
    ExternalServiceUnavailableError,
)
from deribit_price_tracker.core.http_client import BaseHTTPClient
from tests.fakes import FakeAPI, FakeResponse


class FakeAPIClient(BaseHTTPClient):
    """Exposes the protected request method and disables retry delays."""

    def _retry_wait(self) -> wait_base:
        return wait_none()

    async def get_item(self) -> dict:
        return await self._get_json("/item", params={"id": "1"})


@pytest.fixture
def client(fake_api_url: str, http_config: HTTPClientConfig) -> FakeAPIClient:
    return FakeAPIClient(f"{fake_api_url}/v1", http_config)


async def test_builds_url_from_base_url_and_path(
    client: FakeAPIClient, fake_api: FakeAPI
) -> None:
    fake_api.responses = [FakeResponse.json({})]

    async with client:
        await client.get_item()

    assert fake_api.requests == [("/v1/item", {"id": "1"})]


async def test_returns_json_with_decimal_numbers(
    client: FakeAPIClient, fake_api: FakeAPI
) -> None:
    fake_api.responses = [FakeResponse(body='{"price": 123.456789012345678}')]

    async with client:
        result = await client.get_item()

    assert result == {"price": Decimal("123.456789012345678")}


async def test_retries_transient_status_then_succeeds(
    client: FakeAPIClient, fake_api: FakeAPI
) -> None:
    fake_api.responses = [FakeResponse(503), FakeResponse.json({"ok": 1})]

    async with client:
        result = await client.get_item()

    assert result == {"ok": 1}
    assert fake_api.calls == 2


async def test_gives_up_after_configured_attempts(
    client: FakeAPIClient, fake_api: FakeAPI, http_config: HTTPClientConfig
) -> None:
    fake_api.responses = [FakeResponse(503)]

    async with client:
        with pytest.raises(ExternalServiceUnavailableError):
            await client.get_item()

    assert fake_api.calls == http_config.retry_attempts


async def test_client_error_status_is_not_retried(
    client: FakeAPIClient, fake_api: FakeAPI
) -> None:
    fake_api.responses = [FakeResponse(404)]

    async with client:
        with pytest.raises(ExternalServiceError) as exc_info:
            await client.get_item()

    assert not isinstance(exc_info.value, ExternalServiceUnavailableError)
    assert fake_api.calls == 1


async def test_timeout_becomes_unavailable_error(
    client: FakeAPIClient, fake_api: FakeAPI, http_config: HTTPClientConfig
) -> None:
    fake_api.responses = [FakeResponse.json({"ok": 1})]
    fake_api.delay = http_config.timeout * 2

    async with client:
        with pytest.raises(ExternalServiceUnavailableError) as exc_info:
            await client.get_item()

    assert isinstance(exc_info.value.__cause__, TimeoutError)
    assert fake_api.calls == http_config.retry_attempts


async def test_connection_refused_becomes_unavailable_error(
    http_config: HTTPClientConfig,
) -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        free_port = sock.getsockname()[1]
    client = FakeAPIClient(f"http://127.0.0.1:{free_port}", http_config)

    async with client:
        with pytest.raises(ExternalServiceUnavailableError):
            await client.get_item()


async def test_invalid_json_raises_external_service_error(
    client: FakeAPIClient, fake_api: FakeAPI
) -> None:
    fake_api.responses = [FakeResponse(body="<html>oops</html>")]

    async with client:
        with pytest.raises(ExternalServiceError, match="invalid JSON"):
            await client.get_item()


async def test_request_without_context_manager_fails(
    client: FakeAPIClient,
) -> None:
    with pytest.raises(RuntimeError, match="async with"):
        await client.get_item()


async def test_session_is_closed_on_exit(client: FakeAPIClient) -> None:
    async with client:
        session = client._session
        assert session is not None and not session.closed

    assert session.closed
    assert client._session is None


async def test_request_is_logged_with_params_and_status(
    client: FakeAPIClient,
    fake_api: FakeAPI,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake_api.responses = [FakeResponse.json({})]

    with caplog.at_level(logging.INFO):
        async with client:
            await client.get_item()

    assert any(
        record.getMessage().startswith("GET ")
        and "/v1/item {'id': '1'} 200 " in record.getMessage()
        for record in caplog.records
    )

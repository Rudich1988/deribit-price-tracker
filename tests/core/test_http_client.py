import asyncio
import socket
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from decimal import Decimal

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from tenacity import wait_none
from tenacity.wait import wait_base

from deribit_price_tracker.config.http_client import HTTPClientConfig
from deribit_price_tracker.core.exceptions import (
    ExternalServiceError,
    ExternalServiceUnavailableError,
)
from deribit_price_tracker.core.http_client import BaseHTTPClient


class FakeAPIClient(BaseHTTPClient):
    """Exposes the protected request method and disables retry delays."""

    def _retry_wait(self) -> wait_base:
        return wait_none()

    async def get_item(self) -> dict:
        return await self._get_json("/item", params={"id": "1"})


@dataclass
class FakeAPI:
    """Local HTTP server that replies with scripted responses in order."""

    responses: list[web.Response] = field(default_factory=list)
    delay: float = 0
    calls: int = 0

    async def handle(self, request: web.Request) -> web.Response:
        self.calls += 1
        await asyncio.sleep(self.delay)
        if len(self.responses) > 1:
            return self.responses.pop(0)
        return self.responses[0]


@pytest.fixture
def config() -> HTTPClientConfig:
    return HTTPClientConfig(timeout=0.2, connect_timeout=0.2, retry_attempts=3)


@pytest.fixture
def api() -> FakeAPI:
    return FakeAPI()


@pytest.fixture
async def base_url(api: FakeAPI) -> AsyncIterator[str]:
    app = web.Application()
    app.router.add_get("/v1/item", api.handle)
    async with TestServer(app) as server:
        yield str(server.make_url("/v1"))


async def test_returns_json_with_decimal_numbers(
    config: HTTPClientConfig, api: FakeAPI, base_url: str
) -> None:
    api.responses = [web.Response(text='{"price": 123.456789012345678}')]

    async with FakeAPIClient(base_url, config) as client:
        result = await client.get_item()

    assert result == {"price": Decimal("123.456789012345678")}


async def test_retries_transient_status_then_succeeds(
    config: HTTPClientConfig, api: FakeAPI, base_url: str
) -> None:
    api.responses = [web.Response(status=503), web.json_response({"ok": 1})]

    async with FakeAPIClient(base_url, config) as client:
        result = await client.get_item()

    assert result == {"ok": 1}
    assert api.calls == 2


async def test_gives_up_after_configured_attempts(
    config: HTTPClientConfig, api: FakeAPI, base_url: str
) -> None:
    api.responses = [web.Response(status=503)]

    async with FakeAPIClient(base_url, config) as client:
        with pytest.raises(ExternalServiceUnavailableError):
            await client.get_item()

    assert api.calls == config.retry_attempts


async def test_client_error_status_is_not_retried(
    config: HTTPClientConfig, api: FakeAPI, base_url: str
) -> None:
    api.responses = [web.Response(status=404)]

    async with FakeAPIClient(base_url, config) as client:
        with pytest.raises(ExternalServiceError) as exc_info:
            await client.get_item()

    assert not isinstance(exc_info.value, ExternalServiceUnavailableError)
    assert api.calls == 1


async def test_timeout_becomes_unavailable_error(
    config: HTTPClientConfig, api: FakeAPI, base_url: str
) -> None:
    api.responses = [web.json_response({"ok": 1})]
    api.delay = config.timeout * 2

    async with FakeAPIClient(base_url, config) as client:
        with pytest.raises(ExternalServiceUnavailableError) as exc_info:
            await client.get_item()

    assert isinstance(exc_info.value.__cause__, TimeoutError)
    assert api.calls == config.retry_attempts


async def test_connection_refused_becomes_unavailable_error(
    config: HTTPClientConfig,
) -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        free_port = sock.getsockname()[1]

    async with FakeAPIClient(f"http://127.0.0.1:{free_port}", config) as client:
        with pytest.raises(ExternalServiceUnavailableError):
            await client.get_item()


async def test_invalid_json_raises_external_service_error(
    config: HTTPClientConfig, api: FakeAPI, base_url: str
) -> None:
    api.responses = [web.Response(text="<html>oops</html>")]

    async with FakeAPIClient(base_url, config) as client:
        with pytest.raises(ExternalServiceError, match="invalid JSON"):
            await client.get_item()


async def test_request_without_context_manager_fails(
    config: HTTPClientConfig,
) -> None:
    client = FakeAPIClient("http://127.0.0.1", config)

    with pytest.raises(RuntimeError, match="async with"):
        await client.get_item()


async def test_session_is_closed_on_exit(config: HTTPClientConfig) -> None:
    async with FakeAPIClient("http://127.0.0.1", config) as client:
        session = client._session
        assert session is not None and not session.closed

    assert session.closed
    assert client._session is None

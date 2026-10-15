from collections.abc import AsyncIterator

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from deribit_price_tracker.config.http_client import HTTPClientConfig
from tests.fakes import FakeAPI


@pytest.fixture
def http_config() -> HTTPClientConfig:
    return HTTPClientConfig(timeout=0.2, connect_timeout=0.2, retry_attempts=3)


@pytest.fixture
def fake_api() -> FakeAPI:
    return FakeAPI()


@pytest.fixture
async def fake_api_url(fake_api: FakeAPI) -> AsyncIterator[str]:
    app = web.Application()
    app.router.add_route("GET", "/{path:.*}", fake_api.handle)
    async with TestServer(app) as server:
        yield str(server.make_url("")).rstrip("/")

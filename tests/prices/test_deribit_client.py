from decimal import Decimal
from typing import Any

import pytest
from tenacity import wait_none
from tenacity.wait import wait_base

from deribit_price_tracker.config.http_client import HTTPClientConfig
from deribit_price_tracker.core.exceptions import (
    ExternalServiceError,
    ExternalServiceUnavailableError,
)
from deribit_price_tracker.prices.clients import DeribitClient
from deribit_price_tracker.prices.dto import IndexPriceDTO, Ticker
from tests.fakes import FakeAPI, FakeResponse


class FastRetryDeribitClient(DeribitClient):
    def _retry_wait(self) -> wait_base:
        return wait_none()


def price_payload(index_price: Any, **extra: Any) -> dict[str, Any]:
    """Shape of a real public/get_index_price response."""
    return {
        "jsonrpc": "2.0",
        "result": {
            "estimated_delivery_price": index_price,
            "index_price": index_price,
        },
        "usIn": 1792046952551735,
        "usOut": 1792046952552053,
        "usDiff": 318,
        "testnet": False,
        **extra,
    }


def error_payload(code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "error": {"code": code, "message": message},
        "testnet": False,
        "usIn": 1792046953487565,
        "usOut": 1792046953487657,
        "usDiff": 92,
    }


@pytest.fixture
def client(
    fake_api_url: str, http_config: HTTPClientConfig
) -> FastRetryDeribitClient:
    return FastRetryDeribitClient(f"{fake_api_url}/api/v2", http_config)


@pytest.mark.parametrize("ticker", list(Ticker))
async def test_requests_index_price_for_ticker(
    client: DeribitClient, fake_api: FakeAPI, ticker: Ticker
) -> None:
    fake_api.responses = [FakeResponse.json(price_payload(80724.02))]

    async with client:
        await client.get_index_price(ticker)

    assert fake_api.requests == [
        ("/api/v2/public/get_index_price", {"index_name": ticker.value})
    ]


async def test_returns_price_and_exchange_timestamp(
    client: DeribitClient, fake_api: FakeAPI
) -> None:
    fake_api.responses = [FakeResponse.json(price_payload(80724.02))]

    async with client:
        result = await client.get_index_price(Ticker.BTC_USD)

    assert result == IndexPriceDTO(
        ticker=Ticker.BTC_USD,
        price=Decimal("80724.02"),
        timestamp=1792046952,
    )


async def test_accepts_integer_price(
    client: DeribitClient, fake_api: FakeAPI
) -> None:
    fake_api.responses = [FakeResponse.json(price_payload(3000))]

    async with client:
        result = await client.get_index_price(Ticker.ETH_USD)

    assert result.price == Decimal(3000)


async def test_falls_back_to_local_time_without_us_out(
    client: DeribitClient, fake_api: FakeAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = price_payload(80724.02)
    del payload["usOut"]
    fake_api.responses = [FakeResponse.json(payload)]
    monkeypatch.setattr("time.time", lambda: 1700000000.9)

    async with client:
        result = await client.get_index_price(Ticker.BTC_USD)

    assert result.timestamp == 1700000000


async def test_rate_limit_error_is_retried(
    client: DeribitClient, fake_api: FakeAPI
) -> None:
    fake_api.responses = [
        FakeResponse.json(error_payload(10028, "too_many_requests"), 400),
        FakeResponse.json(price_payload(80724.02)),
    ]

    async with client:
        result = await client.get_index_price(Ticker.BTC_USD)

    assert result.price == Decimal("80724.02")
    assert fake_api.calls == 2


async def test_rate_limit_error_gives_up_after_retries(
    client: DeribitClient, fake_api: FakeAPI, http_config: HTTPClientConfig
) -> None:
    fake_api.responses = [
        FakeResponse.json(error_payload(10028, "too_many_requests"), 400)
    ]

    async with client:
        with pytest.raises(ExternalServiceUnavailableError, match="10028"):
            await client.get_index_price(Ticker.BTC_USD)

    assert fake_api.calls == http_config.retry_attempts


async def test_other_json_rpc_error_is_not_retried(
    client: DeribitClient, fake_api: FakeAPI
) -> None:
    fake_api.responses = [
        FakeResponse.json(error_payload(-32602, "Invalid params"), 400)
    ]

    async with client:
        with pytest.raises(ExternalServiceError) as exc_info:
            await client.get_index_price(Ticker.BTC_USD)

    assert not isinstance(exc_info.value, ExternalServiceUnavailableError)
    assert str(exc_info.value) == "Deribit error -32602: Invalid params"
    assert fake_api.calls == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"jsonrpc": "2.0"},
        {"jsonrpc": "2.0", "result": None},
        {"jsonrpc": "2.0", "result": {}},
        price_payload("80724.02"),
        price_payload(None),
        price_payload(True),
    ],
)
async def test_malformed_response_raises_external_service_error(
    client: DeribitClient, fake_api: FakeAPI, payload: dict[str, Any]
) -> None:
    fake_api.responses = [FakeResponse.json(payload)]

    async with client:
        with pytest.raises(ExternalServiceError, match="no index price"):
            await client.get_index_price(Ticker.BTC_USD)

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import httpx2
import pytest
from fastapi import FastAPI

from deribit_price_tracker.app import create_app
from deribit_price_tracker.db.database import Database
from deribit_price_tracker.db.dependencies import get_database
from deribit_price_tracker.prices.dto import IndexPriceDTO, Ticker
from deribit_price_tracker.prices.repositories import PriceRepository


def utc_timestamp(*args: int) -> int:
    return int(datetime(*args, tzinfo=UTC).timestamp())


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx2.AsyncClient]:
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
def no_database(app: FastAPI) -> None:
    """For requests rejected by validation before the database is used."""
    app.dependency_overrides[get_database] = object


@pytest.fixture
def with_database(app: FastAPI, database: Database) -> Database:
    app.dependency_overrides[get_database] = lambda: database
    return database


async def add_prices(
    database: Database, *prices: tuple[Ticker, str, int]
) -> None:
    async with database.session() as session:
        repository = PriceRepository(session)
        for ticker, price, timestamp in prices:
            await repository.add_one(
                IndexPriceDTO(ticker, Decimal(price), timestamp)
            )


# --- Validation (no database needed) ---------------------------------------


@pytest.mark.usefixtures("no_database")
@pytest.mark.parametrize(
    "path", ["/prices", "/prices/latest", "/prices/by-date"]
)
async def test_ticker_is_required(
    client: httpx2.AsyncClient, path: str
) -> None:
    response = await client.get(path)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "ticker"]


@pytest.mark.usefixtures("no_database")
@pytest.mark.parametrize(
    "path", ["/prices", "/prices/latest", "/prices/by-date"]
)
async def test_unknown_ticker_is_rejected(
    client: httpx2.AsyncClient, path: str
) -> None:
    response = await client.get(path, params={"ticker": "doge_usd"})

    assert response.status_code == 422


@pytest.mark.usefixtures("no_database")
async def test_date_from_after_date_to_is_rejected(
    client: httpx2.AsyncClient,
) -> None:
    response = await client.get(
        "/prices/by-date",
        params={
            "ticker": "btc_usd",
            "date_from": "2026-10-16",
            "date_to": "2026-10-15",
        },
    )

    assert response.status_code == 422
    assert "date_from must not be later than date_to" in response.text


@pytest.mark.usefixtures("no_database")
async def test_invalid_date_format_is_rejected(
    client: httpx2.AsyncClient,
) -> None:
    response = await client.get(
        "/prices/by-date", params={"ticker": "btc_usd", "date_from": "15.10.26"}
    )

    assert response.status_code == 422


# --- With the test database ------------------------------------------------


async def test_get_prices_returns_ticker_prices_sorted_by_time(
    client: httpx2.AsyncClient, with_database: Database
) -> None:
    await add_prices(
        with_database,
        (Ticker.BTC_USD, "81000.50", 200),
        (Ticker.ETH_USD, "2353.16", 150),
        (Ticker.BTC_USD, "80724.02", 100),
    )

    response = await client.get("/prices", params={"ticker": "btc_usd"})

    assert response.status_code == 200
    assert response.json() == [
        {"ticker": "btc_usd", "price": 80724.02, "timestamp": 100},
        {"ticker": "btc_usd", "price": 81000.5, "timestamp": 200},
    ]


async def test_get_prices_returns_empty_list_without_data(
    client: httpx2.AsyncClient, with_database: Database
) -> None:
    response = await client.get("/prices", params={"ticker": "eth_usd"})

    assert response.status_code == 200
    assert response.json() == []


async def test_get_latest_price_returns_newest(
    client: httpx2.AsyncClient, with_database: Database
) -> None:
    await add_prices(
        with_database,
        (Ticker.BTC_USD, "80724.02", 100),
        (Ticker.BTC_USD, "81000.50", 200),
        (Ticker.ETH_USD, "2353.16", 300),
    )

    response = await client.get("/prices/latest", params={"ticker": "btc_usd"})

    assert response.status_code == 200
    assert response.json() == {
        "ticker": "btc_usd",
        "price": 81000.5,
        "timestamp": 200,
    }


async def test_get_latest_price_returns_404_without_data(
    client: httpx2.AsyncClient, with_database: Database
) -> None:
    response = await client.get("/prices/latest", params={"ticker": "btc_usd"})

    assert response.status_code == 404
    assert response.json() == {"detail": "No prices saved for btc_usd"}


@pytest.fixture
async def prices_around_october_15(with_database: Database) -> None:
    await add_prices(
        with_database,
        (Ticker.BTC_USD, "1", utc_timestamp(2026, 10, 14, 23, 59, 59)),
        (Ticker.BTC_USD, "2", utc_timestamp(2026, 10, 15, 0, 0, 0)),
        (Ticker.BTC_USD, "3", utc_timestamp(2026, 10, 15, 23, 59, 59)),
        (Ticker.BTC_USD, "4", utc_timestamp(2026, 10, 16, 0, 0, 0)),
        (Ticker.ETH_USD, "9", utc_timestamp(2026, 10, 15, 12, 0, 0)),
    )


@pytest.mark.usefixtures("prices_around_october_15")
@pytest.mark.parametrize(
    ("params", "expected_prices"),
    [
        ({"date_from": "2026-10-15", "date_to": "2026-10-15"}, [2, 3]),
        ({"date_from": "2026-10-14", "date_to": "2026-10-15"}, [1, 2, 3]),
        ({"date_from": "2026-10-15"}, [2, 3, 4]),
        ({"date_to": "2026-10-14"}, [1]),
        ({}, [1, 2, 3, 4]),
        ({"date_from": "2026-10-20", "date_to": "2026-10-21"}, []),
    ],
)
async def test_get_prices_by_date_uses_whole_utc_days(
    client: httpx2.AsyncClient,
    params: dict[str, str],
    expected_prices: list[int],
) -> None:
    response = await client.get(
        "/prices/by-date", params={"ticker": "btc_usd", **params}
    )

    assert response.status_code == 200
    assert [p["price"] for p in response.json()] == expected_prices

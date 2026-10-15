import os
from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
from sqlalchemy import text

from deribit_price_tracker.db.base import ModelBase
from deribit_price_tracker.db.database import Database
from deribit_price_tracker.prices.dto import (
    IndexPriceDTO,
    PriceDTO,
    PricePeriodDTO,
    Ticker,
)
from deribit_price_tracker.prices.repositories import PriceRepository


@pytest.fixture
async def database() -> AsyncIterator[Database]:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    database = Database(url)
    async with database.session() as session:
        connection = await session.connection()
        await connection.run_sync(ModelBase.metadata.create_all)
        await session.execute(text("TRUNCATE prices RESTART IDENTITY"))
    yield database
    await database.dispose()


async def add_prices(database: Database, *prices: IndexPriceDTO) -> None:
    async with database.session() as session:
        repository = PriceRepository(session)
        for price in prices:
            await repository.add_one(price)


def price(ticker: Ticker, value: str, timestamp: int) -> IndexPriceDTO:
    return IndexPriceDTO(
        ticker=ticker, price=Decimal(value), timestamp=timestamp
    )


async def test_add_one_returns_saved_price_with_id(database: Database) -> None:
    async with database.session() as session:
        saved = await PriceRepository(session).add_one(
            price(Ticker.BTC_USD, "80724.02", 100)
        )

    assert saved == PriceDTO(
        id=1, ticker=Ticker.BTC_USD, price=Decimal("80724.02"), timestamp=100
    )


async def test_saved_price_is_committed(database: Database) -> None:
    await add_prices(database, price(Ticker.BTC_USD, "80724.02", 100))

    async with database.session() as session:
        result = await PriceRepository(session).get_all(Ticker.BTC_USD)

    assert [p.price for p in result] == [Decimal("80724.02")]


async def test_get_all_filters_by_ticker_and_sorts_by_time(
    database: Database,
) -> None:
    await add_prices(
        database,
        price(Ticker.BTC_USD, "2", 200),
        price(Ticker.ETH_USD, "9", 150),
        price(Ticker.BTC_USD, "1", 100),
    )

    async with database.session() as session:
        result = await PriceRepository(session).get_all(Ticker.BTC_USD)

    assert [(p.ticker, p.timestamp) for p in result] == [
        (Ticker.BTC_USD, 100),
        (Ticker.BTC_USD, 200),
    ]


async def test_get_latest_returns_newest_price_of_ticker(
    database: Database,
) -> None:
    await add_prices(
        database,
        price(Ticker.BTC_USD, "2", 200),
        price(Ticker.BTC_USD, "1", 100),
        price(Ticker.ETH_USD, "9", 300),
    )

    async with database.session() as session:
        result = await PriceRepository(session).get_latest(Ticker.BTC_USD)

    assert result is not None
    assert (result.price, result.timestamp) == (Decimal("2"), 200)


async def test_get_latest_returns_none_without_prices(
    database: Database,
) -> None:
    async with database.session() as session:
        result = await PriceRepository(session).get_latest(Ticker.BTC_USD)

    assert result is None


async def test_get_by_period_includes_start_and_excludes_end(
    database: Database,
) -> None:
    await add_prices(
        database,
        price(Ticker.BTC_USD, "1", 99),
        price(Ticker.BTC_USD, "2", 100),
        price(Ticker.BTC_USD, "3", 150),
        price(Ticker.BTC_USD, "4", 200),
        price(Ticker.ETH_USD, "9", 150),
    )
    period = PricePeriodDTO(ticker=Ticker.BTC_USD, start=100, end=200)

    async with database.session() as session:
        result = await PriceRepository(session).get_by_period(period)

    assert [p.timestamp for p in result] == [100, 150]

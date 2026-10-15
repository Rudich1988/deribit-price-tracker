from decimal import Decimal

import pytest

from deribit_price_tracker.core.exceptions import NotFoundError
from deribit_price_tracker.prices.dto import (
    IndexPriceDTO,
    PriceDTO,
    PricePeriodDTO,
    Ticker,
)
from deribit_price_tracker.prices.services import PriceService
from tests.fakes import FakePriceRepository


def saved_price(id: int, ticker: Ticker, timestamp: int) -> PriceDTO:
    return PriceDTO(
        id=id, ticker=ticker, price=Decimal("1"), timestamp=timestamp
    )


async def test_add_saves_price() -> None:
    repository = FakePriceRepository()
    service = PriceService(repository)
    price = IndexPriceDTO(Ticker.BTC_USD, Decimal("80724.02"), 100)

    result = await service.add(price)

    assert result == PriceDTO(1, Ticker.BTC_USD, Decimal("80724.02"), 100)
    assert repository.prices == [result]


async def test_get_latest_returns_newest_price() -> None:
    service = PriceService(
        FakePriceRepository(
            [
                saved_price(1, Ticker.BTC_USD, 100),
                saved_price(2, Ticker.BTC_USD, 200),
            ]
        )
    )

    result = await service.get_latest(Ticker.BTC_USD)

    assert result.id == 2


async def test_get_latest_raises_not_found_without_prices() -> None:
    service = PriceService(FakePriceRepository())

    with pytest.raises(NotFoundError, match="btc_usd"):
        await service.get_latest(Ticker.BTC_USD)


async def test_get_all_returns_empty_list_without_prices() -> None:
    service = PriceService(FakePriceRepository())

    assert await service.get_all(Ticker.ETH_USD) == []


async def test_get_by_period_delegates_to_repository() -> None:
    service = PriceService(
        FakePriceRepository(
            [
                saved_price(1, Ticker.BTC_USD, 50),
                saved_price(2, Ticker.BTC_USD, 150),
            ]
        )
    )
    period = PricePeriodDTO(Ticker.BTC_USD, start=100, end=200)

    result = await service.get_by_period(period)

    assert [p.id for p in result] == [2]

import asyncio
import logging
from decimal import Decimal

import pytest

from deribit_price_tracker.core.exceptions import (
    ExternalServiceUnavailableError,
)
from deribit_price_tracker.prices.dto import IndexPriceDTO, Ticker
from deribit_price_tracker.prices.services import PriceCollectionService
from tests.fakes import FakePriceRepository


class FakePriceSource:
    """Returns a scripted price or raises a scripted error per ticker."""

    def __init__(self, results: dict[Ticker, IndexPriceDTO | BaseException]):
        self.results = results
        self.requested: list[Ticker] = []

    async def get_index_price(self, ticker: Ticker) -> IndexPriceDTO:
        self.requested.append(ticker)
        result = self.results[ticker]
        if isinstance(result, BaseException):
            raise result
        return result


BTC = IndexPriceDTO(Ticker.BTC_USD, Decimal("80724.02"), 100)
ETH = IndexPriceDTO(Ticker.ETH_USD, Decimal("2353.16"), 100)


async def test_saves_prices_of_all_tickers() -> None:
    source = FakePriceSource({Ticker.BTC_USD: BTC, Ticker.ETH_USD: ETH})
    repository = FakePriceRepository()

    saved = await PriceCollectionService(source, repository).collect(Ticker)

    assert sorted(source.requested) == sorted(Ticker)
    assert [(p.ticker, p.price) for p in saved] == [
        (Ticker.BTC_USD, Decimal("80724.02")),
        (Ticker.ETH_USD, Decimal("2353.16")),
    ]
    assert repository.prices == saved


async def test_failed_ticker_does_not_block_others(
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = FakePriceSource(
        {
            Ticker.BTC_USD: ExternalServiceUnavailableError("Deribit is down"),
            Ticker.ETH_USD: ETH,
        }
    )
    repository = FakePriceRepository()

    saved = await PriceCollectionService(source, repository).collect(Ticker)

    assert [p.ticker for p in saved] == [Ticker.ETH_USD]
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert [r.getMessage() for r in errors] == [
        "Failed to fetch btc_usd price: Deribit is down"
    ]
    assert errors[0].exc_info is None


async def test_unexpected_error_is_logged_with_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = FakePriceSource(
        {Ticker.BTC_USD: BTC, Ticker.ETH_USD: KeyError("boom")}
    )
    repository = FakePriceRepository()

    saved = await PriceCollectionService(source, repository).collect(Ticker)

    assert [p.ticker for p in saved] == [Ticker.BTC_USD]
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1 and errors[0].exc_info is not None


async def test_nothing_saved_when_all_tickers_fail() -> None:
    error = ExternalServiceUnavailableError("Deribit is down")
    source = FakePriceSource({Ticker.BTC_USD: error, Ticker.ETH_USD: error})
    repository = FakePriceRepository()

    saved = await PriceCollectionService(source, repository).collect(Ticker)

    assert saved == []
    assert repository.prices == []


async def test_cancellation_is_not_swallowed() -> None:
    source = FakePriceSource(
        {Ticker.BTC_USD: asyncio.CancelledError(), Ticker.ETH_USD: ETH}
    )

    with pytest.raises(asyncio.CancelledError):
        await PriceCollectionService(source, FakePriceRepository()).collect(
            Ticker
        )

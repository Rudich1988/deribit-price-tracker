import asyncio
import logging
from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta
from typing import Protocol

from deribit_price_tracker.core.exceptions import AppError, NotFoundError
from deribit_price_tracker.prices.dto import (
    IndexPriceDTO,
    PriceDateFilterDTO,
    PriceDTO,
    PricePeriodDTO,
    Ticker,
)
from deribit_price_tracker.prices.repositories import PriceRepository


class PriceService:
    def __init__(self, repository: PriceRepository) -> None:
        self._repository = repository

    async def add(self, price: IndexPriceDTO) -> PriceDTO:
        return await self._repository.add_one(price)

    async def get_all(self, ticker: Ticker) -> list[PriceDTO]:
        return await self._repository.get_all(ticker)

    async def get_latest(self, ticker: Ticker) -> PriceDTO:
        price = await self._repository.get_latest(ticker)
        if price is None:
            raise NotFoundError(f"No prices saved for {ticker}")
        return price

    async def get_by_period(self, period: PricePeriodDTO) -> list[PriceDTO]:
        return await self._repository.get_by_period(period)

    async def get_by_dates(
        self, date_filter: PriceDateFilterDTO
    ) -> list[PriceDTO]:
        """Prices from the start of date_from to the end of date_to, UTC."""
        period = PricePeriodDTO(
            ticker=date_filter.ticker,
            start=self._day_start(date_filter.date_from),
            end=self._day_start(self._next_day(date_filter.date_to)),
        )
        return await self._repository.get_by_period(period)

    def _day_start(self, day: date | None) -> int | None:
        if day is None:
            return None
        return int(datetime.combine(day, time.min, tzinfo=UTC).timestamp())

    def _next_day(self, day: date | None) -> date | None:
        return day + timedelta(days=1) if day is not None else None


class PriceSource(Protocol):
    """Where current index prices come from (e.g. ``DeribitClient``)."""

    async def get_index_price(self, ticker: Ticker) -> IndexPriceDTO: ...


class PriceCollectionService:
    """Fetches current prices for tickers and saves them.

    Tickers are fetched concurrently and independently: a failure for one
    ticker is logged and does not prevent saving the others.
    """

    _logger = logging.getLogger(__name__)

    def __init__(
        self, source: PriceSource, repository: PriceRepository
    ) -> None:
        self._source = source
        self._repository = repository

    async def collect(self, tickers: Iterable[Ticker]) -> list[PriceDTO]:
        tickers = list(tickers)
        results = await asyncio.gather(
            *(self._source.get_index_price(ticker) for ticker in tickers),
            return_exceptions=True,
        )
        saved = []
        for ticker, result in zip(tickers, results, strict=True):
            if isinstance(result, IndexPriceDTO):
                saved.append(await self._repository.add_one(result))
            elif isinstance(result, Exception):
                self._log_failure(ticker, result)
            else:
                # Not an Exception (e.g. CancelledError): never swallow it.
                raise result
        self._logger.info("Saved %d of %d prices", len(saved), len(tickers))
        return saved

    def _log_failure(self, ticker: Ticker, error: Exception) -> None:
        if isinstance(error, AppError):
            # Expected failure (exchange down, bad response): no traceback.
            self._logger.error("Failed to fetch %s price: %s", ticker, error)
        else:
            self._logger.error(
                "Unexpected error fetching %s price", ticker, exc_info=error
            )

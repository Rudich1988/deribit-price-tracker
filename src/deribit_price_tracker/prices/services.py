from deribit_price_tracker.core.exceptions import NotFoundError
from deribit_price_tracker.prices.dto import (
    IndexPriceDTO,
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

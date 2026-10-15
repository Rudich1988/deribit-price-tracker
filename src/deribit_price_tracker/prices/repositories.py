from sqlalchemy import select

from deribit_price_tracker.prices.dto import (
    IndexPriceDTO,
    PriceDTO,
    PricePeriodDTO,
    Ticker,
)
from deribit_price_tracker.prices.models import Price
from deribit_price_tracker.utils.repository import SQLAlchemyRepository


class PriceRepository(SQLAlchemyRepository):
    model = Price

    async def add_one(self, data: IndexPriceDTO) -> PriceDTO:
        price = self.model(
            ticker=data.ticker.value,
            price=data.price,
            timestamp=data.timestamp,
        )
        self.session.add(price)
        await self.session.flush()
        return self._to_dto(price)

    async def get_all(self, ticker: Ticker) -> list[PriceDTO]:
        query = (
            select(self.model)
            .where(self.model.ticker == ticker.value)
            .order_by(self.model.timestamp, self.model.id)
        )
        return [self._to_dto(price) for price in await self._scalars(query)]

    async def get_latest(self, ticker: Ticker) -> PriceDTO | None:
        query = (
            select(self.model)
            .where(self.model.ticker == ticker.value)
            .order_by(self.model.timestamp.desc(), self.model.id.desc())
            .limit(1)
        )
        price = await self.session.scalar(query)
        return self._to_dto(price) if price is not None else None

    async def get_by_period(self, period: PricePeriodDTO) -> list[PriceDTO]:
        query = select(self.model).where(
            self.model.ticker == period.ticker.value
        )
        if period.start is not None:
            query = query.where(self.model.timestamp >= period.start)
        if period.end is not None:
            query = query.where(self.model.timestamp < period.end)
        query = query.order_by(self.model.timestamp, self.model.id)
        return [self._to_dto(price) for price in await self._scalars(query)]

    async def _scalars(self, query) -> list[Price]:
        return list(await self.session.scalars(query))

    def _to_dto(self, price: Price) -> PriceDTO:
        return PriceDTO(
            id=price.id,
            ticker=Ticker(price.ticker),
            price=price.price,
            timestamp=price.timestamp,
        )

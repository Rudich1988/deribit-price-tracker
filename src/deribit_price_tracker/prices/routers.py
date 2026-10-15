from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Query

from deribit_price_tracker.db.dependencies import DatabaseDep
from deribit_price_tracker.prices.dto import PriceDateFilterDTO, Ticker
from deribit_price_tracker.prices.repositories import PriceRepository
from deribit_price_tracker.prices.schemas import (
    PriceDateFilterQuery,
    PriceResponse,
)
from deribit_price_tracker.prices.services import PriceService

router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("", summary="All saved prices of a ticker")
async def get_prices(
    ticker: Annotated[Ticker, Query()], database: DatabaseDep
) -> list[PriceResponse]:
    async with database.session() as session:
        service = PriceService(PriceRepository(session))
        prices = await service.get_all(ticker)
    return [PriceResponse(**asdict(price)) for price in prices]


@router.get(
    "/latest",
    summary="Latest saved price of a ticker",
    responses={404: {"description": "No prices saved for the ticker"}},
)
async def get_latest_price(
    ticker: Annotated[Ticker, Query()], database: DatabaseDep
) -> PriceResponse:
    async with database.session() as session:
        service = PriceService(PriceRepository(session))
        price = await service.get_latest(ticker)
    return PriceResponse(**asdict(price))


@router.get("/by-date", summary="Prices of a ticker filtered by date")
async def get_prices_by_date(
    query: Annotated[PriceDateFilterQuery, Query()], database: DatabaseDep
) -> list[PriceResponse]:
    date_filter = PriceDateFilterDTO(**query.model_dump())
    async with database.session() as session:
        service = PriceService(PriceRepository(session))
        prices = await service.get_by_dates(date_filter)
    return [PriceResponse(**asdict(price)) for price in prices]

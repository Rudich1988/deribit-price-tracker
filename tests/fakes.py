import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from aiohttp import web

from deribit_price_tracker.prices.dto import (
    IndexPriceDTO,
    PriceDTO,
    PricePeriodDTO,
    Ticker,
)


@dataclass(frozen=True)
class FakeResponse:
    status: int = 200
    body: str = ""

    @classmethod
    def json(cls, payload: Any, status: int = 200) -> "FakeResponse":
        return cls(status=status, body=json.dumps(payload))


@dataclass
class FakeAPI:
    """Local HTTP API that replies with scripted responses in order.

    The last response is repeated once the others are used up.
    """

    responses: list[FakeResponse] = field(default_factory=list)
    delay: float = 0
    requests: list[tuple[str, dict[str, str]]] = field(default_factory=list)

    @property
    def calls(self) -> int:
        return len(self.requests)

    async def handle(self, request: web.Request) -> web.Response:
        self.requests.append((request.path, dict(request.query)))
        await asyncio.sleep(self.delay)
        if len(self.responses) > 1:
            response = self.responses.pop(0)
        else:
            response = self.responses[0]
        return web.Response(
            status=response.status,
            text=response.body,
            content_type="application/json",
        )


class FakePriceRepository:
    """In-memory stand-in for PriceRepository."""

    def __init__(self, prices: list[PriceDTO] | None = None) -> None:
        self.prices = prices or []
        self.requested_periods: list[PricePeriodDTO] = []

    async def add_one(self, data: IndexPriceDTO) -> PriceDTO:
        saved = PriceDTO(id=len(self.prices) + 1, **vars(data))
        self.prices.append(saved)
        return saved

    async def get_all(self, ticker: Ticker) -> list[PriceDTO]:
        return [p for p in self.prices if p.ticker == ticker]

    async def get_latest(self, ticker: Ticker) -> PriceDTO | None:
        prices = await self.get_all(ticker)
        return max(prices, key=lambda p: p.timestamp, default=None)

    async def get_by_period(self, period: PricePeriodDTO) -> list[PriceDTO]:
        self.requested_periods.append(period)
        return [
            p
            for p in await self.get_all(period.ticker)
            if (period.start is None or p.timestamp >= period.start)
            and (period.end is None or p.timestamp < period.end)
        ]

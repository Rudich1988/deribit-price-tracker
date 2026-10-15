from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum


class Ticker(StrEnum):
    """Deribit index names tracked by the application."""

    BTC_USD = "btc_usd"
    ETH_USD = "eth_usd"


@dataclass(frozen=True)
class IndexPriceDTO:
    ticker: Ticker
    price: Decimal
    timestamp: int  # UNIX time, seconds


@dataclass(frozen=True)
class PriceDTO:
    id: int
    ticker: Ticker
    price: Decimal
    timestamp: int  # UNIX time, seconds


@dataclass(frozen=True)
class PricePeriodDTO:
    """Prices of a ticker with start <= timestamp < end (UNIX seconds).

    A bound set to None is not applied.
    """

    ticker: Ticker
    start: int | None = None
    end: int | None = None


@dataclass(frozen=True)
class PriceDateFilterDTO:
    """Prices of a ticker between two calendar dates (UTC), inclusive."""

    ticker: Ticker
    date_from: date | None = None
    date_to: date | None = None

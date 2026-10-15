from dataclasses import dataclass
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
    """Prices of a ticker with start <= timestamp < end (UNIX seconds)."""

    ticker: Ticker
    start: int
    end: int

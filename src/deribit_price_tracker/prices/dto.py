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

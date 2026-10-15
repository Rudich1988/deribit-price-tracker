from decimal import Decimal

from sqlalchemy import BigInteger, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from deribit_price_tracker.db.base import ModelBase


class Price(ModelBase):
    __tablename__ = "prices"
    # Every query filters by ticker and orders or filters by timestamp.
    __table_args__ = (
        Index("ix_prices_ticker_timestamp", "ticker", "timestamp"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16))
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    timestamp: Mapped[int] = mapped_column(BigInteger)

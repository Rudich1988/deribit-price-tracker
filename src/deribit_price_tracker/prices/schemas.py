from datetime import date
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, Field, field_serializer, model_validator

from deribit_price_tracker.prices.dto import Ticker


class PriceResponse(BaseModel):
    ticker: Ticker
    price: Decimal = Field(examples=[80724.02])
    timestamp: int = Field(description="UNIX time, seconds")

    @field_serializer("price")
    def serialize_price(self, price: Decimal) -> float:
        # A JSON number like Deribit returns, instead of a Decimal string
        # with the storage scale ("80724.02000000").
        return float(price)


class PriceDateFilterQuery(BaseModel):
    ticker: Ticker
    date_from: date | None = Field(
        default=None, description="First day, inclusive (UTC)"
    )
    date_to: date | None = Field(
        default=None, description="Last day, inclusive (UTC)"
    )

    @model_validator(mode="after")
    def check_date_order(self) -> Self:
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not be later than date_to")
        return self

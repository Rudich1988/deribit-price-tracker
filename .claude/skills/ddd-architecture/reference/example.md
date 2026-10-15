# Example: `prices` domain, one endpoint through all layers

Illustrative only. Field names are an example, not the real schema.

## models.py

```python
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from deribit_price_tracker.db.base import ModelBase


class Price(ModelBase):
    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(32), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    timestamp: Mapped[datetime]
```

## dto.py

```python
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class PriceCreateDTO:
    ticker: str
    price: Decimal
    timestamp: datetime


@dataclass(frozen=True)
class PriceDTO:
    id: int
    ticker: str
    price: Decimal
    timestamp: datetime
```

## repositories.py

```python
from dataclasses import asdict

from sqlalchemy import select

from deribit_price_tracker.prices.dto import PriceCreateDTO, PriceDTO
from deribit_price_tracker.prices.models import Price
from deribit_price_tracker.utils.repository import SQLAlchemyRepository


class PriceRepository(SQLAlchemyRepository):
    model = Price

    async def add_one(self, data: PriceCreateDTO) -> PriceDTO:
        obj = self.model(**asdict(data))
        self.session.add(obj)
        await self.session.flush()  # fills obj.id, commit is done outside
        return self._to_dto(obj)

    async def get_by_ticker(self, ticker: str) -> list[PriceDTO]:
        query = select(self.model).where(self.model.ticker == ticker)
        result = await self.session.scalars(query)
        return [self._to_dto(obj) for obj in result]

    def _to_dto(self, obj: Price) -> PriceDTO:
        return PriceDTO(
            id=obj.id,
            ticker=obj.ticker,
            price=obj.price,
            timestamp=obj.timestamp,
        )
```

## services.py

```python
from deribit_price_tracker.prices.dto import PriceCreateDTO, PriceDTO
from deribit_price_tracker.prices.repositories import PriceRepository


class PriceService:
    def __init__(self, repository: PriceRepository) -> None:
        self.repository = repository

    async def create(self, data: PriceCreateDTO) -> PriceDTO:
        # business rules go here
        return await self.repository.add_one(data)
```

## schemas.py

```python
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PriceCreate(BaseModel):
    ticker: str
    price: Decimal
    timestamp: datetime


class PriceResponse(BaseModel):
    id: int
    ticker: str
    price: Decimal
    timestamp: datetime
```

## routers.py

```python
from dataclasses import asdict

from fastapi import APIRouter

from deribit_price_tracker.db.dependencies import DatabaseDep
from deribit_price_tracker.prices.dto import PriceCreateDTO
from deribit_price_tracker.prices.repositories import PriceRepository
from deribit_price_tracker.prices.schemas import PriceCreate, PriceResponse
from deribit_price_tracker.prices.services import PriceService

router = APIRouter(prefix="/prices", tags=["prices"])


@router.post("/", response_model=PriceResponse)
async def create_price(
    body: PriceCreate, database: DatabaseDep
) -> PriceResponse:
    data = PriceCreateDTO(**body.model_dump())
    async with database.session() as session:
        service = PriceService(PriceRepository(session))
        result = await service.create(data)
    return PriceResponse(**asdict(result))
```

## app.py

```python
from deribit_price_tracker.prices.routers import router as prices_router

app.include_router(prices_router)
```

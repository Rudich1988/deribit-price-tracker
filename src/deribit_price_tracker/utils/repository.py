from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from deribit_price_tracker.db.base import ModelBase


class AbstractRepository(ABC):
    @abstractmethod
    def __init__(self, session: AsyncSession):
        raise NotImplementedError

    @abstractmethod
    async def add_one(self, data: dict):
        raise NotImplementedError


class SQLAlchemyRepository(AbstractRepository):
    model: type[ModelBase]

    def __init__(self, session: AsyncSession):
        self.session = session

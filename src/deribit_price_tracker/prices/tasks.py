import asyncio

from celery import Celery

from deribit_price_tracker.config.base import Config
from deribit_price_tracker.db.database import Database
from deribit_price_tracker.prices.clients import DeribitClient
from deribit_price_tracker.prices.dto import Ticker
from deribit_price_tracker.prices.repositories import PriceRepository
from deribit_price_tracker.prices.services import PriceCollectionService


class IndexPriceCollectionJob:
    """Entry point of the periodic task: wires dependencies, calls service.

    Like a router, it holds no business logic. Every run gets its own event
    loop (``asyncio.run``), so the HTTP session and the database engine are
    created and closed within one run.
    """

    task_name = "prices.fetch_index_prices"

    def __init__(self, config: Config) -> None:
        self._config = config

    def register(self, app: Celery) -> None:
        # A plain function, not the bound method: Celery builds the task
        # signature from the function and would treat `self` as an argument.
        @app.task(name=self.task_name)
        def fetch_index_prices() -> None:
            self.run()

        interval = self._config.celery.fetch_interval_seconds
        app.conf.beat_schedule[self.task_name] = {
            "task": self.task_name,
            "schedule": interval,
            # A run that waited longer than one interval is outdated:
            # the next scheduled run will fetch fresh prices anyway.
            "options": {"expires": interval},
        }

    def run(self) -> None:
        asyncio.run(self._collect())

    async def _collect(self) -> None:
        database = Database(self._config.database_url, echo=self._config.debug)
        try:
            async with DeribitClient(
                self._config.deribit_base_url, self._config.http_client
            ) as client:
                async with database.session() as session:
                    service = PriceCollectionService(
                        client, PriceRepository(session)
                    )
                    await service.collect(Ticker)
        finally:
            await database.dispose()

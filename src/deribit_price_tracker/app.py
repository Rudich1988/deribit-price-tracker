from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from deribit_price_tracker.config.base import Config
from deribit_price_tracker.core.logging import setup_logging
from deribit_price_tracker.db.database import Database


def create_app() -> FastAPI:
    config = Config.from_env()
    setup_logging(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = Database(config.database_url, echo=config.debug)
        app.state.database = database
        yield
        await database.dispose()

    app = FastAPI(title="Deribit Price Tracker", lifespan=lifespan)

    return app

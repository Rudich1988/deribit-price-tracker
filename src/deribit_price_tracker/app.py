from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from deribit_price_tracker.config.base import Config
from deribit_price_tracker.core.handlers import AppErrorHandler
from deribit_price_tracker.core.logging import setup_logging
from deribit_price_tracker.core.middlewares import (
    RequestLoggingMiddleware,
    UnhandledErrorMiddleware,
)
from deribit_price_tracker.db.database import Database
from deribit_price_tracker.prices.routers import router as prices_router


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
    AppErrorHandler().register(app)
    # The last added middleware is the outermost: logging sees the final
    # status, including the 500 produced by UnhandledErrorMiddleware.
    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.include_router(prices_router)

    return app

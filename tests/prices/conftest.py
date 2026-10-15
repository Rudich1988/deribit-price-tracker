import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text

from deribit_price_tracker.db.base import ModelBase
from deribit_price_tracker.db.database import Database


@pytest.fixture
def test_database_url() -> str:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    return url


@pytest.fixture
async def database(test_database_url: str) -> AsyncIterator[Database]:
    """Empty ``prices`` table in the test database."""
    database = Database(test_database_url)
    async with database.session() as session:
        connection = await session.connection()
        await connection.run_sync(ModelBase.metadata.create_all)
        await session.execute(text("TRUNCATE prices RESTART IDENTITY"))
    yield database
    await database.dispose()

from decimal import Decimal

import pytest

from deribit_price_tracker.config.base import Config
from deribit_price_tracker.db.database import Database
from deribit_price_tracker.prices.dto import Ticker
from deribit_price_tracker.prices.repositories import PriceRepository
from deribit_price_tracker.prices.tasks import IndexPriceCollectionJob
from tests.fakes import FakeAPI, FakeResponse


async def test_job_fetches_and_saves_prices_of_all_tickers(
    monkeypatch: pytest.MonkeyPatch,
    database: Database,
    test_database_url: str,
    fake_api: FakeAPI,
    fake_api_url: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    monkeypatch.setenv("DERIBIT_BASE_URL", f"{fake_api_url}/api/v2")
    fake_api.responses = [
        FakeResponse.json(
            {"result": {"index_price": 80724.02}, "usOut": 1792046952552053}
        )
    ]

    await IndexPriceCollectionJob(Config.from_env())._collect()

    requested = sorted(query["index_name"] for _, query in fake_api.requests)
    assert requested == sorted(Ticker)
    async with database.session() as session:
        repository = PriceRepository(session)
        for ticker in Ticker:
            latest = await repository.get_latest(ticker)
            assert latest is not None
            assert (latest.price, latest.timestamp) == (
                Decimal("80724.02"),
                1792046952,
            )

import pytest

from deribit_price_tracker.celery_app import create_celery_app
from deribit_price_tracker.config.base import Config
from deribit_price_tracker.prices.tasks import IndexPriceCollectionJob


@pytest.fixture
def config(monkeypatch: pytest.MonkeyPatch) -> Config:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://broker:6379/1")
    monkeypatch.setenv("FETCH_INTERVAL_SECONDS", "30")
    return Config.from_env()


def test_uses_broker_from_config(config: Config) -> None:
    app = create_celery_app(config)

    assert app.conf.broker_url == "redis://broker:6379/1"


def test_registers_fetch_task(config: Config) -> None:
    app = create_celery_app(config)

    assert IndexPriceCollectionJob.task_name in app.tasks


def test_schedules_fetch_task_with_interval_from_config(
    config: Config,
) -> None:
    app = create_celery_app(config)

    entry = app.conf.beat_schedule[IndexPriceCollectionJob.task_name]
    assert entry["task"] == IndexPriceCollectionJob.task_name
    assert entry["schedule"] == 30
    assert entry["options"] == {"expires": 30}


def test_keeps_project_logging(config: Config) -> None:
    app = create_celery_app(config)

    assert app.conf.worker_hijack_root_logger is False


def test_scheduled_task_runs_the_job(
    config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs: list[IndexPriceCollectionJob] = []

    def fake_run(job: IndexPriceCollectionJob) -> None:
        runs.append(job)

    monkeypatch.setattr(IndexPriceCollectionJob, "run", fake_run)
    app = create_celery_app(config)
    # Eager mode runs the task in-process, after the same argument check
    # that beat does before sending it to the broker.
    app.conf.task_always_eager = True

    app.tasks[IndexPriceCollectionJob.task_name].apply_async().get()

    assert len(runs) == 1

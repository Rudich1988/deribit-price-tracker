from celery import Celery

from deribit_price_tracker.config.base import Config
from deribit_price_tracker.core.logging import setup_logging
from deribit_price_tracker.prices.tasks import IndexPriceCollectionJob


def create_celery_app(config: Config) -> Celery:
    setup_logging(config)
    app = Celery("deribit_price_tracker", broker=config.celery.broker_url)
    app.conf.update(
        timezone="UTC",
        task_ignore_result=True,
        # Keep the logging configured by setup_logging().
        worker_hijack_root_logger=False,
        broker_connection_retry_on_startup=True,
    )
    IndexPriceCollectionJob(config).register(app)
    return app

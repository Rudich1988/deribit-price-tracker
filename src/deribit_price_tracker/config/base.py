import os
from dataclasses import dataclass

from dotenv import load_dotenv

from deribit_price_tracker.config.celery import CeleryConfig
from deribit_price_tracker.config.http_client import HTTPClientConfig


@dataclass(frozen=True)
class Config:
    database_url: str
    deribit_base_url: str
    debug: bool
    log_level: str
    http_client: HTTPClientConfig
    celery: CeleryConfig

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()
        return cls(
            database_url=os.environ["DATABASE_URL"],
            deribit_base_url=os.getenv(
                "DERIBIT_BASE_URL", "https://www.deribit.com/api/v2"
            ),
            debug=os.getenv("DEBUG", "false").lower() in ("1", "true", "yes"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            http_client=HTTPClientConfig.from_env(),
            celery=CeleryConfig.from_env(),
        )

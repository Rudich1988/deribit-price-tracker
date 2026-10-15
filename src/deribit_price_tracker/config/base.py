import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    database_url: str
    redis_url: str
    deribit_base_url: str
    debug: bool
    log_level: str

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()
        return cls(
            database_url=os.environ["DATABASE_URL"],
            redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
            deribit_base_url=os.getenv(
                "DERIBIT_BASE_URL", "https://www.deribit.com/api/v2"
            ),
            debug=os.getenv("DEBUG", "false").lower() in ("1", "true", "yes"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

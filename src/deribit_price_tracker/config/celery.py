import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CeleryConfig:
    broker_url: str
    fetch_interval_seconds: float

    @classmethod
    def from_env(cls) -> "CeleryConfig":
        return cls(
            broker_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
            fetch_interval_seconds=float(
                os.getenv("FETCH_INTERVAL_SECONDS", "60")
            ),
        )

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class HTTPClientConfig:
    timeout: float
    connect_timeout: float
    retry_attempts: int

    @classmethod
    def from_env(cls) -> "HTTPClientConfig":
        return cls(
            timeout=float(os.getenv("HTTP_TIMEOUT", "10")),
            connect_timeout=float(os.getenv("HTTP_CONNECT_TIMEOUT", "3")),
            retry_attempts=int(os.getenv("HTTP_RETRY_ATTEMPTS", "3")),
        )

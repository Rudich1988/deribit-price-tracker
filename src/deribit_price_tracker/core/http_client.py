import json
import logging
import time
from decimal import Decimal
from types import TracebackType
from typing import Any, ClassVar, Self

import aiohttp
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)
from tenacity.wait import wait_base

from deribit_price_tracker.config.http_client import HTTPClientConfig
from deribit_price_tracker.core.exceptions import (
    ExternalServiceError,
    ExternalServiceUnavailableError,
)


class BaseHTTPClient:
    """Reliable JSON-over-HTTP client to be subclassed per external API.

    Use it as an async context manager: the session (and its connection
    pool) is opened on enter, reused for every request and closed on exit.
    """

    _logger = logging.getLogger(__name__)
    _user_agent: ClassVar[str] = "deribit-price-tracker/0.1"
    _connector_limit: ClassVar[int] = 100
    _connector_limit_per_host: ClassVar[int] = 10
    _transient_statuses: ClassVar[frozenset[int]] = frozenset(
        {429, 502, 503, 504}
    )

    def __init__(self, base_url: str, config: HTTPClientConfig) -> None:
        self._base_url = base_url.rstrip("/")
        self._config = config
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> Self:
        self._session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(
                limit=self._connector_limit,
                limit_per_host=self._connector_limit_per_host,
            ),
            timeout=aiohttp.ClientTimeout(
                total=self._config.timeout,
                connect=self._config.connect_timeout,
            ),
            headers={"User-Agent": self._user_agent},
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def _get_json(
        self, path: str, params: dict[str, str] | None = None
    ) -> Any:
        url = f"{self._base_url}/{path.lstrip('/')}"
        retrying = AsyncRetrying(
            retry=retry_if_exception_type(ExternalServiceUnavailableError),
            stop=stop_after_attempt(self._config.retry_attempts),
            wait=self._retry_wait(),
            before_sleep=self._log_retry,
            reraise=True,
        )
        return await retrying(self._send_get, url, params)

    async def _send_get(self, url: str, params: dict[str, str] | None) -> Any:
        started_at = time.perf_counter()
        try:
            async with self._get_session().get(url, params=params) as response:
                status = response.status
                payload = self._parse_json(await response.text())
        except (aiohttp.ClientConnectionError, TimeoutError) as exc:
            raise ExternalServiceUnavailableError(
                f"GET {url} failed: {type(exc).__name__}"
            ) from exc
        except aiohttp.ClientError as exc:
            raise ExternalServiceError(
                f"GET {url} failed: {type(exc).__name__}"
            ) from exc

        duration_ms = (time.perf_counter() - started_at) * 1000
        self._logger.info(
            "GET %s %s %d %.1fms", url, params or {}, status, duration_ms
        )

        self._raise_for_status(status, payload)
        if payload is None:
            raise ExternalServiceError(f"GET {url} returned invalid JSON")
        return payload

    def _raise_for_status(self, status: int, payload: Any) -> None:
        """Raise for error statuses. Override to parse API error bodies."""
        if status in self._transient_statuses:
            raise ExternalServiceUnavailableError(
                f"Service responded with HTTP {status}"
            )
        if status >= 400:
            raise ExternalServiceError(f"Service responded with HTTP {status}")

    def _parse_json(self, body: str) -> Any:
        # Decimal keeps prices exact, float would round them.
        try:
            return json.loads(body, parse_float=Decimal)
        except ValueError:
            return None

    def _retry_wait(self) -> wait_base:
        return wait_exponential_jitter(multiplier=0.5, max=3)

    def _log_retry(self, retry_state: RetryCallState) -> None:
        self._logger.warning(
            "Retrying request (attempt %d of %d): %s",
            retry_state.attempt_number + 1,
            self._config.retry_attempts,
            retry_state.outcome.exception() if retry_state.outcome else None,
        )

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise RuntimeError(
                f"{type(self).__name__} is not open, use 'async with'"
            )
        return self._session

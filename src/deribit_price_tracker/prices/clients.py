import time
from decimal import Decimal
from typing import Any, ClassVar

from deribit_price_tracker.core.exceptions import (
    ExternalServiceError,
    ExternalServiceUnavailableError,
)
from deribit_price_tracker.core.http_client import BaseHTTPClient
from deribit_price_tracker.prices.dto import IndexPriceDTO, Ticker
from deribit_price_tracker.prices.enums import DeribitErrorCode


class DeribitClient(BaseHTTPClient):
    """Client for the public Deribit JSON-RPC over HTTP API (v2)."""

    _index_price_path: ClassVar[str] = "public/get_index_price"
    _transient_error_codes: ClassVar[frozenset[int]] = frozenset(
        {DeribitErrorCode.TOO_MANY_REQUESTS}
    )
    _microseconds_in_second: ClassVar[int] = 1_000_000

    async def get_index_price(self, ticker: Ticker) -> IndexPriceDTO:
        payload = await self._get_json(
            self._index_price_path, params={"index_name": ticker.value}
        )
        return self._to_dto(ticker, payload)

    def _raise_for_status(self, status: int, payload: Any) -> None:
        # Deribit reports errors in the JSON-RPC body, usually with HTTP 400.
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            code = error.get("code")
            message = f"Deribit error {code}: {error.get('message')}"
            if code in self._transient_error_codes:
                raise ExternalServiceUnavailableError(message)
            raise ExternalServiceError(message)
        super()._raise_for_status(status, payload)

    def _to_dto(self, ticker: Ticker, payload: Any) -> IndexPriceDTO:
        result = payload.get("result") if isinstance(payload, dict) else None
        price = result.get("index_price") if isinstance(result, dict) else None
        if not self._is_number(price):
            raise ExternalServiceError(
                f"Deribit returned no index price for {ticker}"
            )
        return IndexPriceDTO(
            ticker=ticker,
            price=Decimal(price),
            timestamp=self._response_timestamp(payload),
        )

    def _response_timestamp(self, payload: dict[str, Any]) -> int:
        # usOut is the exchange time of the response, in microseconds.
        us_out = payload.get("usOut")
        if isinstance(us_out, int) and not isinstance(us_out, bool):
            return us_out // self._microseconds_in_second
        self._logger.warning("Deribit response has no usOut, using local time")
        return int(time.time())

    def _is_number(self, value: Any) -> bool:
        return isinstance(value, int | Decimal) and not isinstance(value, bool)

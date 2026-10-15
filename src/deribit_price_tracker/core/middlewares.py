import logging
import time
from http import HTTPStatus

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)


class UnhandledErrorMiddleware(BaseHTTPMiddleware):
    """Turns any unexpected exception into a logged 500 response."""

    _logger = logging.getLogger(__name__)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            return await call_next(request)
        except Exception:
            self._logger.exception(
                "Unhandled error on %s %s", request.method, request.url.path
            )
            status = HTTPStatus.INTERNAL_SERVER_ERROR
            return JSONResponse(
                status_code=status, content={"detail": status.phrase}
            )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs method, path, status code and duration of every request."""

    _logger = logging.getLogger(__name__)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        started_at = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started_at) * 1000
        self._logger.info(
            "%s %s %d %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response

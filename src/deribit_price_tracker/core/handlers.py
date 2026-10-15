import logging
from http import HTTPStatus
from typing import ClassVar

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from deribit_price_tracker.core.exceptions import (
    AppError,
    ExternalServiceError,
    ExternalServiceUnavailableError,
    NotFoundError,
)


class AppErrorHandler:
    """Translates domain errors into HTTP responses."""

    _logger = logging.getLogger(__name__)
    _status_codes: ClassVar[dict[type[AppError], HTTPStatus]] = {
        NotFoundError: HTTPStatus.NOT_FOUND,
        ExternalServiceUnavailableError: HTTPStatus.SERVICE_UNAVAILABLE,
        ExternalServiceError: HTTPStatus.BAD_GATEWAY,
    }

    def register(self, app: FastAPI) -> None:
        app.add_exception_handler(AppError, self.handle)

    async def handle(self, request: Request, exc: AppError) -> JSONResponse:
        status = self._status_for(exc)
        if status == HTTPStatus.INTERNAL_SERVER_ERROR:
            self._logger.error("Unmapped application error", exc_info=exc)
            detail = HTTPStatus.INTERNAL_SERVER_ERROR.phrase
        else:
            self._logger.warning("%s: %s", type(exc).__name__, exc.message)
            detail = exc.message
        return JSONResponse(status_code=status, content={"detail": detail})

    def _status_for(self, exc: AppError) -> HTTPStatus:
        for exc_type in type(exc).__mro__:
            if exc_type in self._status_codes:
                return self._status_codes[exc_type]
        return HTTPStatus.INTERNAL_SERVER_ERROR

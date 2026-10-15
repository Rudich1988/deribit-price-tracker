class AppError(Exception):
    """Base class for all expected application errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    """Requested data does not exist."""


class ExternalServiceError(AppError):
    """An external service returned an invalid or error response."""


class ExternalServiceUnavailableError(ExternalServiceError):
    """An external service is temporarily unavailable; retry may help."""

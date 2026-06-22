"""Exception types for the Quartermaster client library."""


class QuartermasterError(Exception):
    """Base exception for Quartermaster client errors."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class APIError(QuartermasterError):
    """HTTP API error with OAuth-style error fields."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error: str | None = None,
        error_description: str | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code)
        self.error = error
        self.error_description = error_description

"""Shared exception types for HTTP error responses."""

from fastapi import HTTPException


class AppError(HTTPException):
    status_code: int = 500

    def __init__(self, detail: str = "Internal server error", code: str | None = None) -> None:
        super().__init__(status_code=self.status_code, detail=detail)
        self.code = code


class NotFound(AppError):
    status_code = 404

    def __init__(self, detail: str = "Not found", code: str | None = None) -> None:
        super().__init__(detail=detail, code=code)


class Forbidden(AppError):
    status_code = 403

    def __init__(self, detail: str = "Forbidden", code: str | None = None) -> None:
        super().__init__(detail=detail, code=code)


class Unauthorized(AppError):
    status_code = 401

    def __init__(self, detail: str = "Unauthorized", code: str | None = None) -> None:
        super().__init__(detail=detail, code=code)


class Conflict(AppError):
    status_code = 409

    def __init__(self, detail: str = "Conflict", code: str | None = None) -> None:
        super().__init__(detail=detail, code=code)


class RateLimited(AppError):
    status_code = 429

    def __init__(self, detail: str = "Rate limit exceeded", code: str | None = None) -> None:
        super().__init__(detail=detail, code=code)

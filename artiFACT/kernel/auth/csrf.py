"""CSRF token generate/validate middleware."""

import hashlib
import hmac
import secrets

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from artiFACT.kernel.config import settings

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"
EXEMPT_PATHS = {"/api/v1/auth/login", "/api/v1/health"}
STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def generate_csrf_token() -> str:
    """Generate a random CSRF token."""
    return secrets.token_hex(32)


def sign_token(token: str) -> str:
    """Sign a CSRF token using the app secret key."""
    return hmac.new(
        settings.SECRET_KEY.encode(), token.encode(), hashlib.sha256
    ).hexdigest()


def set_csrf_cookie(response: Response, token: str) -> None:
    """Set CSRF token as a signed cookie."""
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        samesite="strict",
        secure=(settings.APP_ENV != "development"),
        path="/",
    )


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        if request.method in STATE_CHANGING_METHODS:
            cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
            header_token = request.headers.get(CSRF_HEADER_NAME)

            if not cookie_token or not header_token:
                return JSONResponse(
                    status_code=403, content={"detail": "CSRF token missing"}
                )

            if not hmac.compare_digest(cookie_token, header_token):
                return JSONResponse(
                    status_code=403, content={"detail": "CSRF token mismatch"}
                )

        return await call_next(request)

"""CSRF token generate/validate middleware (pure ASGI)."""

import hashlib
import hmac
import secrets

from typing import Any

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from artiFACT.kernel.config import settings

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"
EXEMPT_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/health",
    "/playground/enter",
    "/playground/reset",
    "/playground/exit",
    "/partials/fact-form",
    "/partials/node-form",
}
STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def generate_csrf_token() -> str:
    """Generate a random CSRF token."""
    return secrets.token_hex(32)


def sign_token(token: str) -> str:
    """Sign a CSRF token using the app secret key."""
    return hmac.new(settings.SECRET_KEY.encode(), token.encode(), hashlib.sha256).hexdigest()


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


class CSRFMiddleware:
    """Pure ASGI middleware for CSRF validation."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        path = request.url.path

        if path in EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        if request.method in STATE_CHANGING_METHODS:
            cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
            header_token = request.headers.get(CSRF_HEADER_NAME)

            if not cookie_token or not header_token:
                response = _json_response(403, {"detail": "CSRF token missing"})
                await response(scope, receive, send)
                return

            if not hmac.compare_digest(cookie_token, header_token):
                response = _json_response(403, {"detail": "CSRF token mismatch"})
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)


def _json_response(status_code: int, body: dict[str, Any]) -> Response:
    """Build a Starlette JSON response."""
    from starlette.responses import JSONResponse

    return JSONResponse(status_code=status_code, content=body)

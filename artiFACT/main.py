"""FastAPI application entry point."""

import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from artiFACT.kernel.auth.csrf import CSRFMiddleware
from artiFACT.kernel.log_forwarder import bind_request_context, configure_structlog
from artiFACT.kernel.security_headers import SecurityHeadersMiddleware
from artiFACT.modules.audit.recorder import register_subscribers as register_audit_subscribers
from artiFACT.modules.audit.router import router as audit_router
from artiFACT.modules.auth_admin.router import router as auth_router
from artiFACT.modules.facts.router import router as facts_router
from artiFACT.modules.queue.badge_counter import register_badge_subscribers
from artiFACT.modules.queue.router import router as queue_router
from artiFACT.modules.search.acronym_miner import (
    register_subscribers as register_search_subscribers,
)
from artiFACT.modules.search.router import partials_router as search_partials_router
from artiFACT.modules.search.router import router as search_router
from artiFACT.modules.ai_chat.router import router as ai_chat_router
from artiFACT.modules.import_pipeline.router import router as import_router
from artiFACT.modules.admin.router import router as admin_router
from artiFACT.modules.export.router import router as export_router
from artiFACT.modules.export.router import sync_router
from artiFACT.modules.signing.router import router as signing_router
from artiFACT.modules.taxonomy.router import partials_router as taxonomy_partials_router
from artiFACT.modules.taxonomy.router import router as taxonomy_router
from artiFACT.pages import router as pages_router

configure_structlog()

app = FastAPI(title="artiFACT", version="0.1.0")

_STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_jinja = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)

app.include_router(auth_router)
app.include_router(taxonomy_router)
app.include_router(taxonomy_partials_router)
app.include_router(facts_router)
app.include_router(audit_router)
app.include_router(queue_router)
app.include_router(search_router)
app.include_router(search_partials_router)
app.include_router(signing_router)
app.include_router(ai_chat_router)
app.include_router(import_router)
app.include_router(export_router)
app.include_router(sync_router)
app.include_router(admin_router)
app.include_router(pages_router)

register_audit_subscribers()
register_badge_subscribers()
register_search_subscribers()


# --- Pure ASGI middleware stack (outermost first) ---
# Order: SecurityHeaders -> RequestID -> CSRF -> App


class RequestIDMiddleware:
    """Pure ASGI middleware to bind a unique request ID."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        bind_request_context(request_id)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_request_id)


# Wrap: CSRF is innermost (closest to app), then RequestID, then SecurityHeaders
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(CSRFMiddleware)


def _is_api_request(request: Request) -> bool:
    """Check if request expects JSON (API) or HTML (browser)."""
    accept = request.headers.get("accept", "")
    return "application/json" in accept or request.url.path.startswith("/api/")


@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc: Exception) -> HTMLResponse | JSONResponse:
    """Custom 401 error page."""
    if _is_api_request(request):
        return JSONResponse(status_code=401, content={"detail": "Authentication required"})
    html = _jinja.get_template("errors/401.html").render()
    return HTMLResponse(html, status_code=401)


@app.exception_handler(403)
async def forbidden_handler(request: Request, exc: Exception) -> HTMLResponse | JSONResponse:
    """Custom 403 error page."""
    if _is_api_request(request):
        return JSONResponse(status_code=403, content={"detail": "Access denied"})
    html = _jinja.get_template("errors/403.html").render()
    return HTMLResponse(html, status_code=403)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> HTMLResponse | JSONResponse:
    """Custom 404 error page."""
    if _is_api_request(request):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    html = _jinja.get_template("errors/404.html").render()
    return HTMLResponse(html, status_code=404)


@app.exception_handler(500)
async def server_error_handler(request: Request, exc: Exception) -> HTMLResponse | JSONResponse:
    """Custom 500 error page."""
    if _is_api_request(request):
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
    html = _jinja.get_template("errors/500.html").render()
    return HTMLResponse(html, status_code=500)


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}

"""ZT Pillar 6 — Structured log configuration for SIEM forwarding."""

import uuid

import structlog


def configure_structlog() -> None:
    """Configure structlog for structured JSON output.

    On VPS (dev): logs go to stdout -> docker compose logs
    On COSMOS (prod): logs go to stdout -> ECS -> CloudWatch -> SIEM
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(0),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def bind_request_context(request_id: str, user_uid: uuid.UUID | None = None) -> None:
    """Bind request-level context for structured log correlation."""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    if user_uid:
        structlog.contextvars.bind_contextvars(user_uid=str(user_uid))

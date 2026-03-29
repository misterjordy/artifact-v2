"""Playground routes: landing, enter, reset, exit."""

from pathlib import Path

import structlog
from fastapi import APIRouter, Cookie, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.csrf import generate_csrf_token, set_csrf_cookie
from artiFACT.kernel.auth.session import create_session, destroy_session, validate_session
from artiFACT.kernel.config import settings
from artiFACT.kernel.db import get_db
from artiFACT.kernel.models import FcUser
from artiFACT.modules.playground.schemas import VALID_ROLES
from artiFACT.modules.playground.service import reset_to_golden

log = structlog.get_logger()

router = APIRouter(tags=["playground"])

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
_jinja = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)

# Map playground role → v2 user cac_dn (used as username in dev mode)
ROLE_TO_USERNAME = {
    "signatory": "dwallace",
    "approver": "omartinez",
    "contributor": "pbeesly",
}


@router.get("/playground", response_class=HTMLResponse)
async def playground_landing(response: Response) -> HTMLResponse:
    """Render the playground landing page with three role cards."""
    csrf_token = generate_csrf_token()
    set_csrf_cookie(response, csrf_token)
    html = _jinja.get_template("playground.html").render(
        csrf_token=csrf_token, active_nav=""
    )
    resp = HTMLResponse(html)
    # Copy CSRF cookie to the HTML response
    set_csrf_cookie(resp, csrf_token)
    return resp


@router.post("/playground/enter")
async def playground_enter(
    response: Response,
    role: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Create a session for the selected playground user."""
    if role not in VALID_ROLES:
        return HTMLResponse("Invalid role", status_code=400)

    username = ROLE_TO_USERNAME[role]
    result = await db.execute(select(FcUser).where(FcUser.cac_dn == username))
    user = result.scalar_one_or_none()

    if not user:
        log.error("playground_user_not_found", username=username)
        return HTMLResponse("Playground user not found. Run seed script first.", status_code=500)

    # TODO: Playground entry bypasses password auth intentionally for demo.
    # Gate behind a feature flag in production.
    session_id = await create_session(user)

    redirect = RedirectResponse("/browse", status_code=303)
    redirect.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="strict",
        secure=(settings.APP_ENV != "development"),
        path="/",
        max_age=8 * 60 * 60,
    )
    redirect.set_cookie(
        key="playground_mode",
        value="true",
        httponly=True,
        samesite="strict",
        secure=(settings.APP_ENV != "development"),
        path="/",
        max_age=8 * 60 * 60,
    )

    csrf_token = generate_csrf_token()
    set_csrf_cookie(redirect, csrf_token)

    return redirect


@router.post("/playground/reset")
async def playground_reset(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session_id: str | None = Cookie(None, alias="session_id"),
    playground_mode: str | None = Cookie(None, alias="playground_mode"),
) -> RedirectResponse:
    """Reset database to golden snapshot. Only available in playground mode."""
    if playground_mode != "true":
        return HTMLResponse("Only playground sessions can reset", status_code=403)

    if not session_id:
        return RedirectResponse("/playground", status_code=303)

    user = await validate_session(session_id, db)
    if not user:
        return RedirectResponse("/playground", status_code=303)

    await reset_to_golden(db)
    await db.commit()

    log.info("playground_reset_by_user", user=user.display_name)
    return RedirectResponse("/browse", status_code=303)


@router.post("/playground/exit")
async def playground_exit(
    session_id: str | None = Cookie(None, alias="session_id"),
    playground_mode: str | None = Cookie(None, alias="playground_mode"),
) -> RedirectResponse:
    """Destroy the playground session and return to landing."""
    if session_id:
        await destroy_session(session_id)

    redirect = RedirectResponse("/playground", status_code=303)
    redirect.delete_cookie("session_id", path="/")
    redirect.delete_cookie("playground_mode", path="/")
    redirect.delete_cookie("csrf_token", path="/")
    return redirect

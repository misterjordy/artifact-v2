"""Auth endpoints: login, logout, current user profile."""

from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.csrf import generate_csrf_token, set_csrf_cookie
from artiFACT.kernel.auth.middleware import get_current_user
from artiFACT.kernel.auth.session import create_session, destroy_session
from artiFACT.kernel.config import settings
from artiFACT.kernel.db import get_db
from artiFACT.kernel.models import FcUser
from artiFACT.kernel.schemas import UserOut
from artiFACT.modules.auth_admin.schemas import LoginRequest, LoginResponse
from artiFACT.modules.auth_admin.service import authenticate_dev

router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.post("/auth/login")
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    session_id: str | None = Cookie(None, alias="session_id"),
) -> LoginResponse:
    user = await authenticate_dev(db, body.username, body.password)

    # Destroy any pre-existing session (e.g. a playground session)
    if session_id:
        await destroy_session(session_id)

    new_session_id = await create_session(user)

    response.set_cookie(
        key="session_id",
        value=new_session_id,
        httponly=True,
        samesite="strict",
        secure=(settings.APP_ENV != "development"),
        path="/",
        max_age=8 * 60 * 60,
    )

    # Clear playground cookie so the banner doesn't bleed into a real login
    response.delete_cookie("playground_mode", path="/")

    csrf_token = generate_csrf_token()
    set_csrf_cookie(response, csrf_token)

    return LoginResponse(
        message="Login successful",
        csrf_token=csrf_token,
        user=UserOut.model_validate(user),
    )


@router.post("/auth/logout")
async def logout(
    response: Response,
    user: FcUser = Depends(get_current_user),
    session_id: str | None = None,
) -> dict[str, str]:
    if session_id:
        await destroy_session(session_id)
    response.delete_cookie("session_id", path="/")
    response.delete_cookie("csrf_token", path="/")
    return {"message": "Logged out"}


@router.get("/users/me")
async def get_me(user: FcUser = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)

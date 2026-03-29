"""Input/output Pydantic models for auth_admin."""

from pydantic import BaseModel

from artiFACT.kernel.schemas import UserOut


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    message: str
    csrf_token: str
    user: UserOut

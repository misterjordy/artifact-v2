"""Pydantic schemas for playground module."""

from pydantic import BaseModel, field_validator


VALID_ROLES = {"signatory", "approver", "contributor"}


class PlaygroundEnter(BaseModel):
    """Role selection for playground entry."""

    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f"Invalid role: {v}. Must be one of {VALID_ROLES}")
        return v

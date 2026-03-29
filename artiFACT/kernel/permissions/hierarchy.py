"""Role hierarchy and comparison logic."""

ROLE_ORDER: list[str] = [
    "viewer",
    "contributor",
    "subapprover",
    "approver",
    "signatory",
    "admin",
]

_ROLE_INDEX: dict[str, int] = {role: i for i, role in enumerate(ROLE_ORDER)}

REQUIRED_ROLES: dict[str, str] = {
    "read": "viewer",
    "contribute": "contributor",
    "approve": "subapprover",
    "sign": "signatory",
    "manage_node": "approver",
    "admin": "admin",
}


def role_gte(role_a: str, role_b: str) -> bool:
    """Return True if role_a >= role_b in the hierarchy."""
    return _ROLE_INDEX.get(role_a, -1) >= _ROLE_INDEX.get(role_b, -1)

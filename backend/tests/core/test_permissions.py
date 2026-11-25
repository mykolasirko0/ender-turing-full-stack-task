import pytest
from fastapi import HTTPException

from app.api.deps import require_permission
from app.core.permissions import (
    ROLE_PERMISSIONS,
    Permission,
    Role,
    has_permission,
    permissions_for,
)
from app.models import User

P = Permission

EXPECTED = {
    Role.ADMIN: {P.USERS_READ, P.USERS_MANAGE, P.METRICS_READ, P.ITEMS_MANAGE_ALL},
    Role.MANAGER: {P.USERS_READ, P.METRICS_READ},
    Role.MEMBER: set(),
}


def _user(role: Role) -> User:
    return User(email=f"{role}@example.com", hashed_password="x", role=role)


def test_every_role_has_a_permission_entry() -> None:
    assert set(ROLE_PERMISSIONS) == set(Role)


def test_permission_values() -> None:
    assert {p.value for p in Permission} == {
        "users:read",
        "users:manage",
        "metrics:read",
        "items:manage_all",
    }


@pytest.mark.parametrize("role", list(Role))
def test_role_permission_matrix(role: Role) -> None:
    assert permissions_for(role) == EXPECTED[role]
    for permission in Permission:
        assert has_permission(_user(role), permission) is (permission in EXPECTED[role])


def test_permissions_for_accepts_plain_string() -> None:
    assert permissions_for("manager") == EXPECTED[Role.MANAGER]  # type: ignore[arg-type]


def test_role_permissions_is_read_only() -> None:
    with pytest.raises(TypeError):
        ROLE_PERMISSIONS[Role.MEMBER] = frozenset(Permission)  # type: ignore[index]


def test_has_permission_ignores_legacy_is_superuser() -> None:
    user = _user(Role.MEMBER)
    user.is_superuser = True
    assert not any(has_permission(user, p) for p in Permission)


def test_require_permission_needs_at_least_one() -> None:
    with pytest.raises(ValueError):
        require_permission()


def test_require_permission_passes_and_returns_user() -> None:
    admin = _user(Role.ADMIN)
    check = require_permission(P.USERS_READ, P.USERS_MANAGE)
    assert check(admin) is admin


def test_require_permission_requires_all_listed() -> None:
    manager = _user(Role.MANAGER)
    # Manager holds users:read but not users:manage -> must be rejected.
    check = require_permission(P.USERS_READ, P.USERS_MANAGE)
    with pytest.raises(HTTPException) as exc:
        check(manager)
    assert exc.value.status_code == 403

    assert require_permission(P.USERS_READ, P.METRICS_READ)(manager) is manager


def test_require_permission_rejects_member() -> None:
    with pytest.raises(HTTPException) as exc:
        require_permission(P.USERS_READ)(_user(Role.MEMBER))
    assert exc.value.status_code == 403

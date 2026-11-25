"""Self-protection and last-admin rules (400), plus signup always yielding member."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.api.routes import users as users_routes
from app.core.config import settings
from app.models import Role, User, UserUpdate
from tests.utils.user import create_random_user, create_user_with_headers
from tests.utils.utils import random_email, random_lower_string

API = settings.API_V1_STR


@pytest.fixture
def admin(client: TestClient, db: Session) -> tuple[User, dict[str, str]]:
    # A fresh admin per test so self-targeted changes can't leak between tests.
    return create_user_with_headers(client=client, db=db, role=Role.ADMIN)


# --- admins cannot demote / deactivate / delete themselves -------------------


@pytest.mark.parametrize("new_role", ["manager", "member"])
def test_admin_cannot_demote_self(
    client: TestClient, db: Session, admin: tuple[User, dict[str, str]], new_role: str
) -> None:
    user, headers = admin
    r = client.patch(f"{API}/users/{user.id}", headers=headers, json={"role": new_role})
    assert r.status_code == 400
    assert r.json()["detail"] == "Admins cannot remove their own admin access"
    db.refresh(user)
    assert user.role == Role.ADMIN


def test_admin_cannot_deactivate_self(
    client: TestClient, db: Session, admin: tuple[User, dict[str, str]]
) -> None:
    user, headers = admin
    r = client.patch(
        f"{API}/users/{user.id}", headers=headers, json={"is_active": False}
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "Admins cannot deactivate themselves"
    db.refresh(user)
    assert user.is_active is True


def test_admin_self_update_without_access_change_is_allowed(
    client: TestClient, admin: tuple[User, dict[str, str]]
) -> None:
    user, headers = admin
    r = client.patch(
        f"{API}/users/{user.id}",
        headers=headers,
        json={"full_name": "Still Admin", "role": "admin", "is_active": True},
    )
    assert r.status_code == 200
    assert r.json()["role"] == "admin"
    assert r.json()["full_name"] == "Still Admin"


def test_admin_cannot_delete_self_by_id(
    client: TestClient, db: Session, admin: tuple[User, dict[str, str]]
) -> None:
    user, headers = admin
    r = client.delete(f"{API}/users/{user.id}", headers=headers)
    assert r.status_code == 400
    assert r.json()["detail"] == "Admins cannot delete themselves"
    assert db.get(User, user.id) is not None


def test_admin_cannot_delete_self_via_me(
    client: TestClient, db: Session, admin: tuple[User, dict[str, str]]
) -> None:
    user, headers = admin
    r = client.delete(f"{API}/users/me", headers=headers)
    assert r.status_code == 400
    assert r.json()["detail"] == "Admins cannot delete themselves"
    assert db.get(User, user.id) is not None


# --- admins can change other admins while another active admin remains -------


def test_admin_can_demote_other_admin(
    client: TestClient, db: Session, admin: tuple[User, dict[str, str]]
) -> None:
    other = create_random_user(db, role=Role.ADMIN)
    r = client.patch(
        f"{API}/users/{other.id}", headers=admin[1], json={"role": "manager"}
    )
    assert r.status_code == 200
    db.refresh(other)
    assert other.role == Role.MANAGER
    assert other.is_superuser is False


def test_admin_can_deactivate_other_admin(
    client: TestClient, db: Session, admin: tuple[User, dict[str, str]]
) -> None:
    other = create_random_user(db, role=Role.ADMIN)
    r = client.patch(
        f"{API}/users/{other.id}", headers=admin[1], json={"is_active": False}
    )
    assert r.status_code == 200
    db.refresh(other)
    assert other.is_active is False


def test_admin_can_delete_other_admin(
    client: TestClient, db: Session, admin: tuple[User, dict[str, str]]
) -> None:
    other = create_random_user(db, role=Role.ADMIN)
    r = client.delete(f"{API}/users/{other.id}", headers=admin[1])
    assert r.status_code == 200


@pytest.mark.parametrize("role", [Role.MANAGER, Role.MEMBER])
def test_non_admin_can_delete_self(client: TestClient, db: Session, role: Role) -> None:
    user, headers = create_user_with_headers(client=client, db=db, role=role)
    user_id = user.id
    r = client.delete(f"{API}/users/me", headers=headers)
    assert r.status_code == 200
    db.expire_all()
    assert db.get(User, user_id) is None


# --- last active admin -------------------------------------------------------
# Sequentially this is unreachable through the API (the acting admin is itself
# an active admin and is covered by the self rules), so the guard is exercised
# directly with the remaining-admin count forced to 0. It protects against
# concurrent requests and future changes to the role -> permission mapping.


@pytest.fixture
def no_other_admins(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    calls: list[object] = []

    def fake_count(**kwargs: object) -> int:
        calls.append(kwargs["exclude_id"])
        return 0

    monkeypatch.setattr(crud, "count_active_users_with_permission", fake_count)
    return calls


def _user(role: Role, *, is_active: bool = True) -> User:
    return User(
        email=random_email(), hashed_password="x", role=role, is_active=is_active
    )


@pytest.mark.parametrize(
    "update",
    [
        UserUpdate(role=Role.MANAGER),
        UserUpdate(role=Role.MEMBER),
        UserUpdate(is_active=False),
    ],
    ids=["demote-manager", "demote-member", "deactivate"],
)
def test_cannot_remove_last_active_admin_on_update(
    db: Session, no_other_admins: list[object], update: UserUpdate
) -> None:
    actor, target = _user(Role.ADMIN), _user(Role.ADMIN)
    with pytest.raises(HTTPException) as exc:
        users_routes._check_admin_rules_for_update(
            session=db, actor=actor, target=target, user_in=update
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot remove the last active admin"
    assert no_other_admins == [target.id]


def test_cannot_delete_last_active_admin(
    db: Session, no_other_admins: list[object]
) -> None:
    actor, target = _user(Role.ADMIN), _user(Role.ADMIN)
    with pytest.raises(HTTPException) as exc:
        users_routes._check_admin_rules_for_delete(
            session=db, actor=actor, target=target
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot remove the last active admin"
    assert no_other_admins == [target.id]


@pytest.mark.parametrize(
    ("target", "update"),
    [
        (_user(Role.ADMIN, is_active=False), UserUpdate(role=Role.MEMBER)),
        (_user(Role.ADMIN), UserUpdate(full_name="x")),
        (_user(Role.ADMIN), UserUpdate(role=Role.ADMIN, is_active=True)),
        (_user(Role.MANAGER), UserUpdate(is_active=False)),
        (_user(Role.MEMBER), UserUpdate(role=Role.MANAGER)),
    ],
    ids=["inactive-admin", "no-access-change", "noop", "manager", "member"],
)
def test_last_admin_guard_not_triggered(
    db: Session, no_other_admins: list[object], target: User, update: UserUpdate
) -> None:
    users_routes._check_admin_rules_for_update(
        session=db, actor=_user(Role.ADMIN), target=target, user_in=update
    )
    assert no_other_admins == []


def test_count_active_admins(db: Session) -> None:
    before = crud.count_active_users_with_permission(
        session=db, permission=users_routes.ADMIN_PERMISSION
    )
    admin = create_random_user(db, role=Role.ADMIN)
    create_random_user(db, role=Role.MANAGER)
    after = crud.count_active_users_with_permission(
        session=db, permission=users_routes.ADMIN_PERMISSION
    )
    assert after == before + 1
    excluded = crud.count_active_users_with_permission(
        session=db, permission=users_routes.ADMIN_PERMISSION, exclude_id=admin.id
    )
    assert excluded == before
    crud.update_user(session=db, db_user=admin, user_in=UserUpdate(is_active=False))
    assert (
        crud.count_active_users_with_permission(
            session=db, permission=users_routes.ADMIN_PERMISSION
        )
        == before
    )


# --- signup ----------------------------------------------------------------


@pytest.mark.parametrize(
    "extra",
    [{}, {"role": "admin"}, {"is_superuser": True}, {"role": "manager"}],
    ids=["plain", "role-admin", "is-superuser", "role-manager"],
)
def test_signup_always_creates_member(
    client: TestClient, db: Session, extra: dict[str, object]
) -> None:
    email = random_email()
    data = {"email": email, "password": random_lower_string(), **extra}
    r = client.post(f"{API}/users/signup", json=data)
    assert r.status_code == 200
    assert r.json()["role"] == "member"
    user = crud.get_user_by_email(session=db, email=email)
    assert user
    assert user.role == Role.MEMBER
    assert user.is_superuser is False

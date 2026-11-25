"""API exposes `role` (+ `permissions` on /users/me); `is_superuser` is internal only."""

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import Role
from tests.utils.user import create_random_user, create_user_with_headers
from tests.utils.utils import random_email, random_lower_string

API = settings.API_V1_STR


# --- /users/me ---------------------------------------------------------------


def test_me_admin_permissions(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(f"{API}/users/me", headers=superuser_token_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "admin"
    assert body["permissions"] == [
        "items:manage_all",
        "metrics:read",
        "users:manage",
        "users:read",
    ]


def test_me_manager_permissions(client: TestClient, db: Session) -> None:
    _, headers = create_user_with_headers(client=client, db=db, role=Role.MANAGER)
    body = client.get(f"{API}/users/me", headers=headers).json()
    assert body["role"] == "manager"
    assert body["permissions"] == ["metrics:read", "users:read"]


def test_me_member_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    body = client.get(f"{API}/users/me", headers=normal_user_token_headers).json()
    assert body["role"] == "member"
    assert body["permissions"] == []


# --- is_superuser is not part of the API --------------------------------------


def test_openapi_has_role_and_no_is_superuser(client: TestClient) -> None:
    schemas = client.get(f"{API}/openapi.json").json()["components"]["schemas"]
    for name in ("UserPublic", "UserCreate", "UserUpdate", "UserMe"):
        props = schemas[name]["properties"]
        assert "role" in props, name
        assert "is_superuser" not in props, name
    assert "permissions" in schemas["UserMe"]["properties"]
    assert "permissions" not in schemas["UserPublic"]["properties"]


def test_list_users_exposes_role_only(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(f"{API}/users/", headers=superuser_token_headers)
    assert r.status_code == 200
    for user in r.json()["data"]:
        assert user["role"] in {"admin", "manager", "member"}
        assert "is_superuser" not in user
        assert "permissions" not in user


def test_admin_creates_user_with_role(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    email = random_email()
    r = client.post(
        f"{API}/users/",
        headers=superuser_token_headers,
        json={"email": email, "password": random_lower_string(), "role": "manager"},
    )
    assert r.status_code == 200
    assert r.json()["role"] == "manager"
    assert "is_superuser" not in r.json()
    user = crud.get_user_by_email(session=db, email=email)
    assert user
    assert user.role == Role.MANAGER
    assert user.is_superuser is False


def test_create_user_ignores_is_superuser_payload(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    email = random_email()
    r = client.post(
        f"{API}/users/",
        headers=superuser_token_headers,
        json={"email": email, "password": random_lower_string(), "is_superuser": True},
    )
    assert r.status_code == 200
    assert r.json()["role"] == "member"
    user = crud.get_user_by_email(session=db, email=email)
    assert user
    assert user.is_superuser is False


def test_create_user_rejects_unknown_role(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{API}/users/",
        headers=superuser_token_headers,
        json={
            "email": random_email(),
            "password": random_lower_string(),
            "role": "owner",
        },
    )
    assert r.status_code == 422


def test_admin_updates_role_syncs_legacy_flag(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    user = create_random_user(db)
    r = client.patch(
        f"{API}/users/{user.id}",
        headers=superuser_token_headers,
        json={"role": "admin"},
    )
    assert r.status_code == 200
    assert r.json()["role"] == "admin"
    db.refresh(user)
    assert user.role == Role.ADMIN
    assert user.is_superuser is True


# --- members cannot change their own role / is_active ------------------------


ME = f"{API}/users/me"


def test_update_me_rejects_role(client: TestClient, db: Session) -> None:
    user, headers = create_user_with_headers(client=client, db=db, role=Role.MEMBER)
    r = client.patch(ME, headers=headers, json={"role": "admin"})
    assert r.status_code == 422
    db.refresh(user)
    assert user.role == Role.MEMBER


def test_update_me_rejects_is_active(client: TestClient, db: Session) -> None:
    user, headers = create_user_with_headers(client=client, db=db, role=Role.MEMBER)
    r = client.patch(ME, headers=headers, json={"is_active": False})
    assert r.status_code == 422
    db.refresh(user)
    assert user.is_active is True


def test_update_me_rejects_is_superuser(client: TestClient, db: Session) -> None:
    user, headers = create_user_with_headers(client=client, db=db, role=Role.MEMBER)
    r = client.patch(ME, headers=headers, json={"full_name": "x", "is_superuser": True})
    assert r.status_code == 422
    db.refresh(user)
    assert user.is_superuser is False
    assert user.full_name != "x"


def test_update_me_still_allows_profile_fields(client: TestClient, db: Session) -> None:
    user, headers = create_user_with_headers(client=client, db=db, role=Role.MEMBER)
    r = client.patch(ME, headers=headers, json={"full_name": "New Name"})
    assert r.status_code == 200
    assert r.json()["full_name"] == "New Name"
    assert r.json()["role"] == "member"
    db.refresh(user)
    assert user.full_name == "New Name"

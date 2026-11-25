"""Route guards per role: admin / manager / member.

Endpoint-specific behaviour is covered in test_users.py / test_items.py; this
module only checks who is let through each permission-guarded endpoint.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import ItemCreate, Role, User
from tests.utils.item import create_random_item
from tests.utils.user import create_random_user, create_user_with_headers
from tests.utils.utils import random_email, random_lower_string

API = settings.API_V1_STR


@pytest.fixture(scope="module")
def manager(client: TestClient, db: Session) -> tuple[User, dict[str, str]]:
    return create_user_with_headers(client=client, db=db, role=Role.MANAGER)


@pytest.fixture(scope="module")
def member(client: TestClient, db: Session) -> tuple[User, dict[str, str]]:
    return create_user_with_headers(client=client, db=db, role=Role.MEMBER)


# --- users:read ------------------------------------------------------------


def test_list_users_allowed_for_admin_and_manager(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    manager: tuple[User, dict[str, str]],
) -> None:
    for headers in (superuser_token_headers, manager[1]):
        r = client.get(f"{API}/users/", headers=headers)
        assert r.status_code == 200
        assert r.json()["count"] >= 1


def test_list_users_forbidden_for_member(
    client: TestClient, member: tuple[User, dict[str, str]]
) -> None:
    r = client.get(f"{API}/users/", headers=member[1])
    assert r.status_code == 403


def test_manager_can_read_other_user(
    client: TestClient, db: Session, manager: tuple[User, dict[str, str]]
) -> None:
    other = create_random_user(db)
    r = client.get(f"{API}/users/{other.id}", headers=manager[1])
    assert r.status_code == 200
    assert r.json()["id"] == str(other.id)


def test_manager_reading_missing_user_gets_404(
    client: TestClient, manager: tuple[User, dict[str, str]]
) -> None:
    r = client.get(f"{API}/users/{uuid.uuid4()}", headers=manager[1])
    assert r.status_code == 404


def test_member_cannot_read_other_user(
    client: TestClient, db: Session, member: tuple[User, dict[str, str]]
) -> None:
    other = create_random_user(db)
    r = client.get(f"{API}/users/{other.id}", headers=member[1])
    assert r.status_code == 403


@pytest.mark.parametrize("role", [Role.MEMBER, Role.MANAGER])
def test_user_can_read_self_by_id_without_users_read(
    client: TestClient, db: Session, role: Role
) -> None:
    user, headers = create_user_with_headers(client=client, db=db, role=role)
    r = client.get(f"{API}/users/{user.id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == str(user.id)


# --- users:manage ----------------------------------------------------------


def test_manager_cannot_create_user(
    client: TestClient, manager: tuple[User, dict[str, str]]
) -> None:
    data = {"email": random_email(), "password": random_lower_string()}
    r = client.post(f"{API}/users/", headers=manager[1], json=data)
    assert r.status_code == 403


def test_manager_cannot_update_user(
    client: TestClient, db: Session, manager: tuple[User, dict[str, str]]
) -> None:
    other = create_random_user(db)
    r = client.patch(
        f"{API}/users/{other.id}", headers=manager[1], json={"full_name": "x"}
    )
    assert r.status_code == 403


def test_manager_cannot_change_own_role(
    client: TestClient, db: Session, manager: tuple[User, dict[str, str]]
) -> None:
    user, _ = manager
    r = client.patch(
        f"{API}/users/{user.id}", headers=manager[1], json={"role": "admin"}
    )
    assert r.status_code == 403
    db.refresh(user)
    assert user.role == Role.MANAGER


def test_manager_cannot_delete_user(
    client: TestClient, db: Session, manager: tuple[User, dict[str, str]]
) -> None:
    other = create_random_user(db)
    r = client.delete(f"{API}/users/{other.id}", headers=manager[1])
    assert r.status_code == 403


def test_password_recovery_html_requires_users_manage(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    manager: tuple[User, dict[str, str]],
) -> None:
    # Unknown email: an admin gets past the guard to the route's 404. (The
    # success path is not exercised here: the route builds an invalid
    # "subject:" response header upstream and crashes - pre-existing bug.)
    url = f"{API}/password-recovery-html-content/{random_email()}"
    assert client.post(url, headers=manager[1]).status_code == 403
    assert client.post(url, headers=superuser_token_headers).status_code == 404


def test_test_email_requires_users_manage(
    client: TestClient, manager: tuple[User, dict[str, str]]
) -> None:
    r = client.post(
        f"{API}/utils/test-email/",
        headers=manager[1],
        params={"email_to": random_email()},
    )
    assert r.status_code == 403


# --- items:manage_all ------------------------------------------------------


def test_manager_sees_only_own_items(
    client: TestClient, db: Session, manager: tuple[User, dict[str, str]]
) -> None:
    user, headers = manager
    create_random_item(db)  # owned by someone else
    crud.create_item(
        session=db,
        item_in=ItemCreate(title=random_lower_string()),
        owner_id=user.id,
    )
    r = client.get(f"{API}/items/", headers=headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data
    assert all(item["owner_id"] == str(user.id) for item in data)


@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_manager_cannot_touch_others_item(
    client: TestClient,
    db: Session,
    manager: tuple[User, dict[str, str]],
    method: str,
) -> None:
    item = create_random_item(db)
    kwargs = {"json": {"title": "x"}} if method == "put" else {}
    r = client.request(
        method.upper(), f"{API}/items/{item.id}", headers=manager[1], **kwargs
    )
    assert r.status_code == 403


def test_admin_can_read_others_item(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    item = create_random_item(db)
    r = client.get(f"{API}/items/{item.id}", headers=superuser_token_headers)
    assert r.status_code == 200


# --- legacy flag is never used for authorization ---------------------------


def test_legacy_is_superuser_flag_grants_nothing(
    client: TestClient, db: Session
) -> None:
    user, headers = create_user_with_headers(client=client, db=db, role=Role.MEMBER)
    # Bypass crud (which would re-sync the flag) to simulate drifted data.
    user.is_superuser = True
    db.add(user)
    db.commit()

    assert client.get(f"{API}/users/", headers=headers).status_code == 403
    other_item = create_random_item(db)
    r = client.get(f"{API}/items/{other_item.id}", headers=headers)
    assert r.status_code == 403

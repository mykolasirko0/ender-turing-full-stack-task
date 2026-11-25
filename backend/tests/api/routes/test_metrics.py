import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import Role, UserUpdate
from tests.utils.user import create_random_user, create_user_with_headers

URL = f"{settings.API_V1_STR}/metrics/"


@pytest.mark.parametrize("role", [Role.ADMIN, Role.MANAGER])
def test_metrics_allowed(client: TestClient, db: Session, role: Role) -> None:
    _, headers = create_user_with_headers(client=client, db=db, role=role)
    r = client.get(URL, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert set(body["users_by_role"]) == {"admin", "manager", "member"}
    assert sum(body["users_by_role"].values()) == body["total_users"]
    assert 0 < body["active_users"] <= body["total_users"]


def test_metrics_forbidden_for_member(client: TestClient, db: Session) -> None:
    _, headers = create_user_with_headers(client=client, db=db, role=Role.MEMBER)
    assert client.get(URL, headers=headers).status_code == 403


def test_metrics_requires_auth(client: TestClient) -> None:
    assert client.get(URL).status_code == 401


def test_metrics_counts_change(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    before = client.get(URL, headers=superuser_token_headers).json()

    create_random_user(db, role=Role.MANAGER)
    inactive_member = create_random_user(db, role=Role.MEMBER)
    crud.update_user(
        session=db, db_user=inactive_member, user_in=UserUpdate(is_active=False)
    )

    after = client.get(URL, headers=superuser_token_headers).json()
    assert after["total_users"] == before["total_users"] + 2
    assert after["active_users"] == before["active_users"] + 1
    assert after["users_by_role"]["manager"] == before["users_by_role"]["manager"] + 1
    assert after["users_by_role"]["member"] == before["users_by_role"]["member"] + 1
    assert after["users_by_role"]["admin"] == before["users_by_role"]["admin"]

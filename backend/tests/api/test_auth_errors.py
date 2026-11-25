"""401 vs 403: 401 when not (or no longer) authenticated, 403 when lacking a permission."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlmodel import Session

from app import crud
from app.core import security
from app.core.config import settings
from app.models import Role, UserUpdate
from tests.utils.user import create_user_with_headers

ME = f"{settings.API_V1_STR}/users/me"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _token(payload: dict[str, object], key: str = settings.SECRET_KEY) -> str:
    return jwt.encode(payload, key, algorithm=security.ALGORITHM)


def _assert_401(r: Response) -> None:
    assert r.status_code == 401
    assert r.headers.get("www-authenticate") == "Bearer"


def test_missing_token_is_401(client: TestClient) -> None:
    _assert_401(client.get(ME))


@pytest.mark.parametrize(
    "token",
    [
        "garbage",
        _token({"sub": str(uuid.uuid4())}, key="not-the-secret-key-0123456789abcd"),
        _token(
            {
                "sub": str(uuid.uuid4()),
                "exp": datetime.now(UTC) - timedelta(minutes=1),
            }
        ),
        _token({"exp": datetime.now(UTC) + timedelta(minutes=5)}),  # no sub
        _token({"sub": "not-a-uuid", "exp": datetime.now(UTC) + timedelta(minutes=5)}),
    ],
    ids=["malformed", "wrong-key", "expired", "no-sub", "non-uuid-sub"],
)
def test_invalid_token_is_401(client: TestClient, token: str) -> None:
    r = client.get(ME, headers=_bearer(token))
    _assert_401(r)
    assert r.json()["detail"] == "Could not validate credentials"


def test_token_for_deleted_user_is_401(client: TestClient, db: Session) -> None:
    user, headers = create_user_with_headers(client=client, db=db, role=Role.MEMBER)
    db.delete(user)
    db.commit()
    r = client.get(ME, headers=headers)
    _assert_401(r)
    assert r.json()["detail"] == "User not found"


def test_token_for_inactive_user_is_401(client: TestClient, db: Session) -> None:
    user, headers = create_user_with_headers(client=client, db=db, role=Role.MEMBER)
    crud.update_user(session=db, db_user=user, user_in=UserUpdate(is_active=False))
    r = client.get(ME, headers=headers)
    _assert_401(r)
    assert r.json()["detail"] == "Inactive user"


def test_missing_permission_is_403_not_401(client: TestClient, db: Session) -> None:
    _, headers = create_user_with_headers(client=client, db=db, role=Role.MEMBER)
    r = client.get(f"{settings.API_V1_STR}/users/", headers=headers)
    assert r.status_code == 403
    assert "www-authenticate" not in r.headers

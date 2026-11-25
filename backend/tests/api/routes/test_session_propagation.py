"""Role / is_active changes apply to already-issued tokens on the next request.

The JWT only carries the user id; the user (and so their role) is reloaded from
the DB on every request. These tests pin that behaviour: one token is issued up
front and reused across every change.
"""

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import Role
from tests.utils.user import create_user_with_headers

API = settings.API_V1_STR


def test_role_and_active_changes_apply_to_existing_token(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    user, token = create_user_with_headers(client=client, db=db, role=Role.MEMBER)
    admin = superuser_token_headers

    def set_user(**changes: object) -> None:
        r = client.patch(f"{API}/users/{user.id}", headers=admin, json=changes)
        assert r.status_code == 200, r.text

    def me() -> dict[str, object]:
        r = client.get(f"{API}/users/me", headers=token)
        assert r.status_code == 200, r.text
        body: dict[str, object] = r.json()
        return body

    # member: no access to users or metrics
    assert client.get(f"{API}/users/", headers=token).status_code == 403
    assert client.get(f"{API}/metrics/", headers=token).status_code == 403

    # promoted to manager -> same token can read users and metrics, not manage
    set_user(role="manager")
    assert me()["role"] == "manager"
    assert me()["permissions"] == ["metrics:read", "users:read"]
    assert client.get(f"{API}/users/", headers=token).status_code == 200
    assert client.get(f"{API}/metrics/", headers=token).status_code == 200
    r = client.patch(f"{API}/users/{user.id}", headers=token, json={"full_name": "x"})
    assert r.status_code == 403

    # promoted to admin -> same token can manage users
    set_user(role="admin")
    r = client.patch(f"{API}/users/{user.id}", headers=token, json={"full_name": "x"})
    assert r.status_code == 200

    # demoted back to member -> access removed immediately
    set_user(role="member")
    assert me()["permissions"] == []
    assert client.get(f"{API}/users/", headers=token).status_code == 403

    # deactivated -> same token is rejected as unauthenticated (401)
    set_user(is_active=False)
    r = client.get(f"{API}/users/me", headers=token)
    assert r.status_code == 401
    assert r.json()["detail"] == "Inactive user"

    # reactivated -> the old token works again (not yet expired)
    set_user(is_active=True)
    assert me()["role"] == "member"


def test_deactivating_user_revokes_existing_token_for_all_routes(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    user, token = create_user_with_headers(client=client, db=db, role=Role.MANAGER)
    r = client.patch(
        f"{API}/users/{user.id}",
        headers=superuser_token_headers,
        json={"is_active": False},
    )
    assert r.status_code == 200
    for path in ("/users/me", "/users/", "/metrics/", "/items/"):
        assert client.get(f"{API}{path}", headers=token).status_code == 401, path

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud, demo_data
from app.core.config import settings
from app.core.security import verify_password
from app.models import Role, User, UserUpdate


@pytest.fixture
def clean_demo_users(db: Session) -> Generator[None]:
    def remove() -> None:
        for demo in demo_data.DEMO_USERS:
            user = crud.get_user_by_email(session=db, email=demo.email)
            if user:
                db.delete(user)
        db.commit()

    remove()
    yield
    remove()


def _get(db: Session, email: str) -> User:
    db.expire_all()
    user = crud.get_user_by_email(session=db, email=email)
    assert user
    return user


@pytest.mark.usefixtures("clean_demo_users")
def test_seed_creates_then_is_idempotent(db: Session) -> None:
    assert demo_data.seed_demo_users(db) == {
        "manager@example.com": "created",
        "member@example.com": "created",
    }
    manager = _get(db, "manager@example.com")
    member = _get(db, "member@example.com")
    assert (manager.role, member.role) == (Role.MANAGER, Role.MEMBER)
    assert manager.is_active and member.is_active
    assert verify_password(demo_data.DEMO_PASSWORD, manager.hashed_password)[0]
    first_hash = manager.hashed_password

    assert demo_data.seed_demo_users(db) == {
        "manager@example.com": "unchanged",
        "member@example.com": "unchanged",
    }
    # No needless re-hash on a no-op run.
    assert _get(db, "manager@example.com").hashed_password == first_hash


@pytest.mark.usefixtures("clean_demo_users")
def test_seed_resets_drifted_demo_user(db: Session) -> None:
    demo_data.seed_demo_users(db)
    manager = _get(db, "manager@example.com")
    crud.update_user(
        session=db,
        db_user=manager,
        user_in=UserUpdate(role=Role.MEMBER, is_active=False, password="other-pass"),
    )

    result = demo_data.seed_demo_users(db)
    assert result["manager@example.com"] == "updated"
    assert result["member@example.com"] == "unchanged"
    manager = _get(db, "manager@example.com")
    assert manager.role == Role.MANAGER
    assert manager.is_active is True
    assert verify_password(demo_data.DEMO_PASSWORD, manager.hashed_password)[0]


@pytest.mark.usefixtures("clean_demo_users")
def test_demo_credentials_log_in(client: TestClient, db: Session) -> None:
    demo_data.seed_demo_users(db)
    for demo in demo_data.DEMO_USERS:
        r = client.post(
            f"{settings.API_V1_STR}/login/access-token",
            data={"username": demo.email, "password": demo_data.DEMO_PASSWORD},
        )
        assert r.status_code == 200, demo.email
        me = client.get(
            f"{settings.API_V1_STR}/users/me",
            headers={"Authorization": f"Bearer {r.json()['access_token']}"},
        ).json()
        assert me["role"] == demo.role.value


@pytest.mark.parametrize("env", [None, "production", "staging"])
def test_main_refuses_outside_development(
    monkeypatch: pytest.MonkeyPatch, env: str | None
) -> None:
    monkeypatch.setattr(settings, "FASTAPI_ENV", env)

    def fail_seed(_: Session) -> None:
        raise AssertionError("must not seed outside development")

    monkeypatch.setattr(demo_data, "seed_demo_users", fail_seed)
    with pytest.raises(SystemExit) as exc:
        demo_data.main()
    assert exc.value.code == 1


@pytest.mark.usefixtures("clean_demo_users")
def test_main_runs_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "FASTAPI_ENV", "development")
    demo_data.main()  # no SystemExit

"""Create (or reset) a demo manager and a demo member for local testing.

Idempotent: re-running brings both users back to the documented state
(role, active, name, password) and reports what changed. Refuses to run
outside local development (FASTAPI_ENV=development).

Usage (from the backend container):  python app/demo_data.py
"""

import logging
import sys
from dataclasses import dataclass
from typing import Literal

from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.core.db import engine
from app.core.permissions import Role
from app.core.security import verify_password
from app.models import UserCreate, UserUpdate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEMO_PASSWORD = "demo-password"

Action = Literal["created", "updated", "unchanged"]


@dataclass(frozen=True)
class DemoUser:
    email: str
    full_name: str
    role: Role


DEMO_USERS: tuple[DemoUser, ...] = (
    DemoUser(email="manager@example.com", full_name="Demo Manager", role=Role.MANAGER),
    DemoUser(email="member@example.com", full_name="Demo Member", role=Role.MEMBER),
)


def is_allowed_environment() -> bool:
    return settings.FASTAPI_ENV == "development"


def _ensure_demo_user(session: Session, demo: DemoUser) -> Action:
    user = crud.get_user_by_email(session=session, email=demo.email)
    if user is None:
        crud.create_user(
            session=session,
            user_create=UserCreate(
                email=demo.email,
                full_name=demo.full_name,
                password=DEMO_PASSWORD,
                role=demo.role,
            ),
        )
        return "created"

    password_ok, _ = verify_password(DEMO_PASSWORD, user.hashed_password)
    in_desired_state = (
        user.role == demo.role
        and user.is_active
        and user.full_name == demo.full_name
        and password_ok
    )
    if in_desired_state:
        return "unchanged"

    update = UserUpdate(full_name=demo.full_name, role=demo.role, is_active=True)
    if not password_ok:
        # Set only when needed: an explicit password=None would count as "set"
        # and be hashed by crud.update_user.
        update.password = DEMO_PASSWORD
    crud.update_user(session=session, db_user=user, user_in=update)
    return "updated"


def seed_demo_users(session: Session) -> dict[str, Action]:
    return {demo.email: _ensure_demo_user(session, demo) for demo in DEMO_USERS}


def main() -> None:
    if not is_allowed_environment():
        logger.error(
            "Refusing to create demo users: FASTAPI_ENV is %r, expected 'development'",
            settings.FASTAPI_ENV,
        )
        sys.exit(1)
    with Session(engine) as session:
        results = seed_demo_users(session)
    for email, action in results.items():
        logger.info("%s: %s (password: %s)", email, action, DEMO_PASSWORD)


if __name__ == "__main__":
    main()

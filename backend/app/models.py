import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from pydantic import ConfigDict, EmailStr, field_validator
from sqlmodel import Field, Relationship, SQLModel

from app.core.permissions import Permission

# Re-exported so `from app.models import Role` keeps working; Role lives in
# app.core.permissions to avoid a models <-> permissions import cycle.
from app.core.permissions import Role as Role


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


ROLE_CHECK_SQL = "role IN ('admin', 'manager', 'member')"


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    role: Role = Field(
        default=Role.MEMBER,
        # Non-native enum: stored as VARCHAR(20) (CHECK lives in __table_args__),
        # but loaded back as Role instead of a plain str.
        sa_type=sa.Enum(
            Role,
            native_enum=False,
            create_constraint=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        sa_column_kwargs={"server_default": Role.MEMBER.value},
    )
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    role: Role | None = None
    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)

    # These may be omitted but not sent as null: the columns are NOT NULL (and a
    # null password can't be hashed), so a null would otherwise be a 500.
    # role: null is still accepted and means "leave unchanged" (see crud).
    @field_validator("email", "is_active", "password", mode="before")
    @classmethod
    def _reject_explicit_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("may be omitted but must not be null")
        return value


class UserUpdateMe(SQLModel):
    # Reject unknown fields (e.g. role, is_active) instead of silently dropping
    # them, so self-service privilege changes fail loudly with 422.
    # Must be set via model_config: the `class X(SQLModel, extra=...)` form is
    # silently ignored by SQLModel's metaclass. SQLModel types model_config as
    # its private SQLModelConfig (ConfigDict + table-only keys), so the public
    # ConfigDict needs an ignore for each type checker.
    model_config = ConfigDict(extra="forbid")  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)

    # email may be omitted but not null (NOT NULL column -> would be a 500).
    # full_name: null stays valid and clears the name.
    @field_validator("email", mode="before")
    @classmethod
    def _reject_explicit_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("may be omitted but must not be null")
        return value


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    __table_args__ = (sa.CheckConstraint(ROLE_CHECK_SQL, name="ck_user_role"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    # Legacy column, kept in sync by crud (role == admin). Never used for
    # authorization and not exposed through the API.
    is_superuser: bool = False
    created_at: datetime | None = Field(default_factory=get_datetime_utc)
    items: list[Item] = Relationship(back_populates="owner", cascade_delete=True)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


# Current user, with the permissions their role grants (for the frontend to mirror)
class UserMe(UserPublic):
    permissions: list[Permission]


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


class UserMetrics(SQLModel):
    total_users: int
    active_users: int
    # Every role is present, with 0 when no user has it.
    users_by_role: dict[Role, int]


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(default_factory=get_datetime_utc)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)

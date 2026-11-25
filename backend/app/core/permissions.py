"""Roles, permissions and the mapping between them.

Authorization decisions must go through ``has_permission`` (or the
``require_permission`` dependency in ``app.api.deps``), never through role
names or the legacy ``is_superuser`` flag.
"""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import User


class Role(StrEnum):
    ADMIN = "admin"
    MANAGER = "manager"
    MEMBER = "member"


class Permission(StrEnum):
    USERS_READ = "users:read"
    USERS_MANAGE = "users:manage"
    METRICS_READ = "metrics:read"
    ITEMS_MANAGE_ALL = "items:manage_all"


# Listed explicitly per role (rather than "admin gets everything") so that a
# newly added permission is never granted to anyone by accident.
ROLE_PERMISSIONS: Mapping[Role, frozenset[Permission]] = MappingProxyType(
    {
        Role.ADMIN: frozenset(
            {
                Permission.USERS_READ,
                Permission.USERS_MANAGE,
                Permission.METRICS_READ,
                Permission.ITEMS_MANAGE_ALL,
            }
        ),
        Role.MANAGER: frozenset(
            {
                Permission.USERS_READ,
                Permission.METRICS_READ,
            }
        ),
        Role.MEMBER: frozenset(),
    }
)


def permissions_for(role: Role) -> frozenset[Permission]:
    return ROLE_PERMISSIONS[Role(role)]


def has_permission(user: User, permission: Permission) -> bool:
    return permission in permissions_for(user.role)

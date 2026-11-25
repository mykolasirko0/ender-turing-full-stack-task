from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import col, func, select

from app.api.deps import SessionDep, require_permission
from app.core.permissions import Permission, Role
from app.models import User, UserMetrics

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get(
    "/",
    dependencies=[Depends(require_permission(Permission.METRICS_READ))],
    response_model=UserMetrics,
)
def read_metrics(session: SessionDep) -> Any:
    """
    Basic user counts (total, active, per role).
    """
    total_users = session.exec(select(func.count()).select_from(User)).one()
    active_users = session.exec(
        select(func.count()).select_from(User).where(col(User.is_active))
    ).one()
    rows = session.exec(select(User.role, func.count()).group_by(User.role)).all()
    users_by_role = dict.fromkeys(Role, 0) | {Role(role): count for role, count in rows}
    return UserMetrics(
        total_users=total_users,
        active_users=active_users,
        users_by_role=users_by_role,
    )

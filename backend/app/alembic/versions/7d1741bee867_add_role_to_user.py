"""Add role to User

Revision ID: 7d1741bee867
Revises: fe56fa70289e
Create Date: 2026-11-25 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7d1741bee867'
down_revision = 'fe56fa70289e'
branch_labels = None
depends_on = None

# Inlined rather than imported from app.models so this migration stays
# stable if the application's role list changes later.
ROLE_CHECK_SQL = "role IN ('admin', 'manager', 'member')"


def upgrade():
    op.add_column(
        'user',
        sa.Column(
            'role',
            sa.String(length=20),
            nullable=False,
            server_default='member',
        ),
    )
    op.execute("""UPDATE "user" SET role = 'admin' WHERE is_superuser""")
    op.create_check_constraint('ck_user_role', 'user', ROLE_CHECK_SQL)


def downgrade():
    # Re-derive is_superuser from role so admins created after the upgrade
    # (and demoted superusers) keep correct privileges on the old schema.
    op.execute("""UPDATE "user" SET is_superuser = (role = 'admin')""")
    op.drop_constraint('ck_user_role', 'user', type_='check')
    op.drop_column('user', 'role')

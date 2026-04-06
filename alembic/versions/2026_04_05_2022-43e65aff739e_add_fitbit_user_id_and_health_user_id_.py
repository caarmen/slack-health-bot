"""Add fitbit_user_id and health_user_id to fitbit_users

Revision ID: 43e65aff739e
Revises: 08b4c0449799
Create Date: 2026-04-05 19:03:36.786130

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "43e65aff739e"
down_revision = "f02452713b7f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("fitbit_users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("fitbit_user_id", sa.String(length=40), nullable=True)
        )
        batch_op.add_column(
            sa.Column("health_user_id", sa.String(length=63), nullable=True)
        )
    op.execute("UPDATE fitbit_users SET fitbit_user_id = oauth_userid")


def downgrade() -> None:
    with op.batch_alter_table("fitbit_users", schema=None) as batch_op:
        batch_op.drop_column("health_user_id")
        batch_op.drop_column("fitbit_user_id")

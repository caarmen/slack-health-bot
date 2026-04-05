"""Increase fitbit access and refresh token size

Revision ID: 08b4c0449799
Revises: b161afec4dfd
Create Date: 2026-04-05 19:01:53.701154

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "08b4c0449799"
down_revision = "b161afec4dfd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("fitbit_users", schema=None) as batch_op:
        batch_op.alter_column(
            "oauth_access_token",
            existing_type=sa.VARCHAR(length=40),
            type_=sa.String(length=512),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "oauth_refresh_token",
            existing_type=sa.VARCHAR(length=40),
            type_=sa.String(length=512),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("fitbit_users", schema=None) as batch_op:
        batch_op.alter_column(
            "oauth_refresh_token",
            existing_type=sa.String(length=512),
            type_=sa.VARCHAR(length=40),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "oauth_access_token",
            existing_type=sa.String(length=512),
            type_=sa.VARCHAR(length=40),
            existing_nullable=True,
        )

"""add-fitbit-latest-activities

Revision ID: 52f924fa8700
Revises: 8b790aed140e
Create Date: 2023-08-05 18:02:56.523865

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "52f924fa8700"
down_revision = "8b790aed140e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "fitbit_latest_activities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("log_id", sa.Integer(), nullable=False),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("total_minutes", sa.Integer(), nullable=False),
        sa.Column("calories", sa.Integer(), nullable=False),
        sa.Column("fat_burn_minutes", sa.Integer(), nullable=True),
        sa.Column("cardio_minutes", sa.Integer(), nullable=True),
        sa.Column("peak_minutes", sa.Integer(), nullable=True),
        sa.Column("out_of_range_minutes", sa.Integer(), nullable=True),
        sa.Column("fitbit_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["fitbit_user_id"], ["fitbit_users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fitbit_user_id", "type_id"),
        sa.UniqueConstraint("log_id"),
    )
    op.create_index(
        op.f("ix_fitbit_latest_activities_id"),
        "fitbit_latest_activities",
        ["id"],
        unique=False,
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(
        op.f("ix_fitbit_latest_activities_id"), table_name="fitbit_latest_activities"
    )
    op.drop_table("fitbit_latest_activities")
    # ### end Alembic commands ###

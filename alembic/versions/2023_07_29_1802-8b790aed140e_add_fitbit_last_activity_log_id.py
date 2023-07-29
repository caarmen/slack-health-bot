"""add-fitbit-last_activity_log_id

Revision ID: 8b790aed140e
Revises: de8be1ac65a5
Create Date: 2023-07-29 18:02:14.247379

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "8b790aed140e"
down_revision = "de8be1ac65a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "fitbit_users", sa.Column("last_activity_log_id", sa.Integer(), nullable=True)
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("fitbit_users", "last_activity_log_id")
    # ### end Alembic commands ###
"""add-withings-last-weight

Revision ID: d70a420a9a98
Revises: 50bf112899a7
Create Date: 2023-06-11 14:02:17.211658

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "d70a420a9a98"
down_revision = "50bf112899a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("withings_users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("last_weight", sa.Float(), nullable=True))

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("withings_users", schema=None) as batch_op:
        batch_op.drop_column("last_weight")

    # ### end Alembic commands ###

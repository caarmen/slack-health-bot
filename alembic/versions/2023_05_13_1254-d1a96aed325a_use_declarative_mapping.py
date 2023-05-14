"""use declarative mapping

Revision ID: d1a96aed325a
Revises: e1da2ea0086f
Create Date: 2023-05-13 12:54:04.773019

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d1a96aed325a"
down_revision = "e1da2ea0086f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("slack_alias", existing_type=sa.VARCHAR(), nullable=False)
        batch_op.alter_column(
            "oauth_userid", existing_type=sa.VARCHAR(length=40), nullable=False
        )

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "oauth_userid", existing_type=sa.VARCHAR(length=40), nullable=True
        )
        batch_op.alter_column("slack_alias", existing_type=sa.VARCHAR(), nullable=True)

    # ### end Alembic commands ###

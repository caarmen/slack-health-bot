"""add_fitbit_activities_distance_km

Revision ID: 22857e6099f4
Revises: 77dca2f35afa
Create Date: 2024-07-26 22:14:38.959111

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "22857e6099f4"
down_revision = "77dca2f35afa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("fitbit_activities", schema=None) as batch_op:
        batch_op.add_column(sa.Column("distance_km", sa.Float(), nullable=True))

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("fitbit_activities", schema=None) as batch_op:
        batch_op.drop_column("distance_km")

    # ### end Alembic commands ###

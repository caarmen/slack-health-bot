"""add fitbit_activities.logged_at and make fitbit_daily_activities use it

Revision ID: b161afec4dfd
Revises: ae34520a342d
Create Date: 2026-03-08 19:03:16.861755

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "b161afec4dfd"
down_revision = "ae34520a342d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the view which references fitbit_activities.
    op.execute("DROP VIEW IF EXISTS fitbit_daily_activities")

    # Add the logged_at column, first as nullable.
    with op.batch_alter_table("fitbit_activities", schema=None) as batch_op:
        batch_op.add_column(sa.Column("logged_at", sa.DateTime(), nullable=True))
    # Set the logged_at column to the value of created_at.
    op.execute("UPDATE fitbit_activities set logged_at = created_at")
    # Now that logged_at is populated everywhere, make it not nullable.
    with op.batch_alter_table("fitbit_activities", schema=None) as batch_op:
        batch_op.alter_column("logged_at", nullable=False)

    # Recreate the view, this time using logged_at instead of updated_at.
    op.execute(
        """
        CREATE VIEW fitbit_daily_activities AS
            SELECT
                fitbit_user_id,
                type_id,
                date(logged_at) as date,
                count(*) as count_activities,
                sum(calories) as sum_calories,
                sum(distance_km) as sum_distance_km,
                sum(total_minutes) as sum_total_minutes,
                sum(fat_burn_minutes) as sum_fat_burn_minutes,
                sum(cardio_minutes) as sum_cardio_minutes,
                sum(peak_minutes) as sum_peak_minutes,
                sum(out_of_zone_minutes) as sum_out_of_zone_minutes
            FROM
                fitbit_activities
            GROUP BY
                fitbit_user_id,
                type_id,
                date(logged_at)
        """
    )


def downgrade() -> None:
    # Drop the view which references fitbit_activities.
    op.execute("DROP VIEW IF EXISTS fitbit_daily_activities")

    # Remove the logged_at column.
    with op.batch_alter_table("fitbit_activities", schema=None) as batch_op:
        batch_op.drop_column("logged_at")
    # Make the view use updated_at again, instead of logged_at.
    op.execute(
        """
        CREATE VIEW fitbit_daily_activities AS
            SELECT
                fitbit_user_id,
                type_id,
                date(updated_at) as date,
                count(*) as count_activities,
                sum(calories) as sum_calories,
                sum(distance_km) as sum_distance_km,
                sum(total_minutes) as sum_total_minutes,
                sum(fat_burn_minutes) as sum_fat_burn_minutes,
                sum(cardio_minutes) as sum_cardio_minutes,
                sum(peak_minutes) as sum_peak_minutes,
                sum(out_of_zone_minutes) as sum_out_of_zone_minutes
            FROM
                fitbit_activities
            GROUP BY
                fitbit_user_id,
                type_id,
                date(updated_at)
        """
    )

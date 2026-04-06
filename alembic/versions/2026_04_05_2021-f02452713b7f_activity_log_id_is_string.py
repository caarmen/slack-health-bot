"""activity log_id is string

Revision ID: f02452713b7f
Revises: 43e65aff739e
Create Date: 2026-04-05 20:21:37.598409

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "f02452713b7f"
down_revision = "08b4c0449799"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the view which references fitbit_activities.
    op.execute("DROP VIEW IF EXISTS fitbit_daily_activities")

    with op.batch_alter_table("fitbit_activities", schema=None) as batch_op:
        batch_op.alter_column(
            "log_id",
            existing_type=sa.INTEGER(),
            type_=sa.String(length=80),
            existing_nullable=False,
        )

    # Recreate the view
    op.execute("""
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
        """)


def downgrade() -> None:
    # Drop the view which references fitbit_activities.
    op.execute("DROP VIEW IF EXISTS fitbit_daily_activities")

    with op.batch_alter_table("fitbit_activities", schema=None) as batch_op:
        batch_op.alter_column(
            "log_id",
            existing_type=sa.String(length=80),
            type_=sa.INTEGER(),
            existing_nullable=False,
        )

    # Recreate the view
    op.execute("""
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
        """)

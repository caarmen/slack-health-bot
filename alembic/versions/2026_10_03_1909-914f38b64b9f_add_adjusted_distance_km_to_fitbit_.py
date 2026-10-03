"""Add adjusted_distance_km to fitbit_daily_activities view

Revision ID: 914f38b64b9f
Revises: 23a4cfad31a3
Create Date: 2026-10-03 19:09:29.962392

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "914f38b64b9f"
down_revision = "23a4cfad31a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the view to recreate it
    op.execute("DROP VIEW IF EXISTS fitbit_daily_activities")

    # Use a CTE to avoid having to do the date(logged_at) calculation
    # in the join clause, when matching fitbit_activities' logged_at
    # field to distance_account's date field.
    op.execute("""
        CREATE VIEW fitbit_daily_activities AS
            WITH fitbit_activities_ext AS (
                SELECT
                    fitbit_user_id,
                    type_id,
                    date(logged_at) as date,
                    calories,
                    distance_km,
                    total_minutes,
                    fat_burn_minutes,
                    cardio_minutes,
                    peak_minutes,
                    out_of_zone_minutes
                FROM
                    fitbit_activities
            )
            SELECT
                fitbit_activities_ext.fitbit_user_id,
                fitbit_activities_ext.type_id,
                fitbit_activities_ext.date,
                count(*) as count_activities,
                sum(calories) as sum_calories,
                sum(distance_km) as sum_distance_km,
                sum(distance_km) + distance_account.debit_km as adjusted_distance_km,
                sum(total_minutes) as sum_total_minutes,
                sum(fat_burn_minutes) as sum_fat_burn_minutes,
                sum(cardio_minutes) as sum_cardio_minutes,
                sum(peak_minutes) as sum_peak_minutes,
                sum(out_of_zone_minutes) as sum_out_of_zone_minutes
            FROM
                fitbit_activities_ext
            LEFT OUTER JOIN
                distance_account ON
                    fitbit_activities_ext.fitbit_user_id = distance_account.fitbit_user_id
                    AND fitbit_activities_ext.type_id = distance_account.type_id
                    AND fitbit_activities_ext.date = distance_account.date
            GROUP BY
                fitbit_activities_ext.fitbit_user_id,
                fitbit_activities_ext.type_id,
                fitbit_activities_ext.date
        """)


def downgrade() -> None:
    # Drop the view to recreate it
    op.execute("DROP VIEW IF EXISTS fitbit_daily_activities")

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

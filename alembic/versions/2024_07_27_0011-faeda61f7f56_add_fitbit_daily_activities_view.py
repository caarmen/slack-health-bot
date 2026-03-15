"""add_fitbit_daily_activities_view

Revision ID: faeda61f7f56
Revises: 77dca2f35afa
Create Date: 2024-07-21 00:11:31.689478

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "faeda61f7f56"
down_revision = "22857e6099f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
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
                sum(out_of_range_minutes) as sum_out_of_range_minutes
            FROM
                fitbit_activities
            GROUP BY
                fitbit_user_id,
                type_id,
                date(updated_at)
        """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS fitbit_daily_activities")

"""
One-shot data migration task to populate credits in the DistanceAccount model/table.

The logic:

1. Find any activity types which have a distance_km configured in "goals".
2. Find any lines in fitbit_daily_activities for these activity types whose sum_distance_km exceeds the goal,
   and for which no line exists yet in distance_accounts with a credit_km.
3. Create entries in distance_accounts for these user/activity type/dates, with the value if sum_distance_km - the goal.
"""

import argparse
import asyncio
import datetime as dt
from dataclasses import dataclass
from typing import Sequence

from dependency_injector.wiring import Provide, inject
from sqlalchemy import and_, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from slackhealthbot.containers import Container
from slackhealthbot.data.database import models
from slackhealthbot.settings import AppSettings


@dataclass
class Args:
    """Command-line arguments."""

    dry_run: bool = False


@dataclass
class ActivityTypeConfig:
    """Goal configuration for an activity type."""

    type_id: int
    minimum_distance_km: float


@dataclass
class Lookup:
    """Lookup keys for fitbit_daily_activites and distance_account."""

    fitbit_user_id: int
    date: dt.date
    type_id: int


@dataclass
class Credit:
    """Credit to apply for the given lookup."""

    lookup: Lookup
    credit_km: float


def parse_args() -> Args:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Create entries in the distance_account tables when km goals have been exceeded."
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return Args(
        dry_run=args.dry_run,
    )


async def do_migration(args: Args):
    """Starting point for the migration."""
    activity_type_configs = read_activity_type_configs()
    for activity_type_config in activity_type_configs:
        missing_credits = await find_missing_credits(activity_type_config)
        await create_credits(
            credits=missing_credits,
            is_dry_run=args.dry_run,
        )


@inject
def read_activity_type_configs(
    app_settings: AppSettings = Provide[Container.app_settings],
):
    """Find all activity types which have a distance goal configured."""
    return [
        ActivityTypeConfig(
            type_id=x.id,
            minimum_distance_km=x.report.daily_goals.distance_km,
        )
        for x in app_settings.fitbit.activities.activity_types
        if x.report and x.report.daily_goals.distance_km
    ]


def select_daily_activities_join_distance_account():
    """
    Create a select statement on the fitbit_daily_activites joined with distance_account.
    """
    return select(
        models.FitbitDailyActivity.fitbit_user_id,
        models.FitbitDailyActivity.date,
        models.FitbitDailyActivity.sum_distance_km,
    ).join(
        models.DistanceAccount,
        and_(
            models.FitbitDailyActivity.fitbit_user_id
            == models.DistanceAccount.fitbit_user_id,
            models.FitbitDailyActivity.date == models.DistanceAccount.date,
            models.FitbitDailyActivity.type_id == models.DistanceAccount.type_id,
        ),
        isouter=True,
    )


@inject
async def find_missing_credits(
    activity_type_config: ActivityTypeConfig,
    db: AsyncSession = Provide[Container.db],
) -> Sequence[Credit]:
    """Find all credits that need to be applied."""
    _log(f"find_missing_credits for {activity_type_config}")

    # Find all daily activities exceeding the distance goal
    # and which have no corresponding credit entry.
    query = select_daily_activities_join_distance_account().where(
        and_(
            models.FitbitDailyActivity.sum_distance_km
            > activity_type_config.minimum_distance_km,
            models.DistanceAccount.credit_km
            == None,  # noqa E711 (sqlalchemy needs this)
            models.FitbitDailyActivity.type_id == activity_type_config.type_id,
        )
    )
    rows = (await db.execute(query)).mappings().fetchall()

    # Map the results.
    return [
        Credit(
            lookup=Lookup(
                fitbit_user_id=row["fitbit_user_id"],
                date=row["date"],
                type_id=activity_type_config.type_id,
            ),
            credit_km=row["sum_distance_km"] - activity_type_config.minimum_distance_km,
        )
        for row in rows
    ]


@inject
async def create_credits(
    credits: Sequence[Credit],
    is_dry_run: bool,
    db: AsyncSession = Provide[Container.db],
):
    _log(f"Create {len(credits)} credits: is_dry_run={is_dry_run}")
    if not credits:
        return
    # https://docs.sqlalchemy.org/en/21/_modules/examples/performance/bulk_inserts.html
    insert_values = [
        {
            "fitbit_user_id": x.lookup.fitbit_user_id,
            "type_id": x.lookup.type_id,
            "date": x.lookup.date,
            "credit_km": x.credit_km,
        }
        for x in credits
    ]
    await db.execute(insert(models.DistanceAccount).values(insert_values))

    # Only commit the changes if we're not in dry run.
    if is_dry_run:
        await db.rollback()
    else:
        await db.flush()
        await db.commit()


def _log(message: str):
    print(message)


async def main(container: Container | None = None):
    """
    :param container: Container for dependency injection.
        Leave as None for executing the migration from the command line.
        Provide a Container instance when calling this function from tests.
    """
    args = parse_args()
    if container is None:
        container = Container()
    container.wire(modules=[__name__])
    await do_migration(args)


if __name__ == "__main__":
    asyncio.run(main())

from dependency_injector.wiring import Provide, inject

from slackhealthbot.containers import Container
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
)
from slackhealthbot.domain.models.activity import DailyActivityStats
from slackhealthbot.settings import Settings


@inject
async def do(
    daily_activity: DailyActivityStats,
    settings: Settings = Provide[Container.settings],
    local_fitbit_repo: LocalFitbitRepository = Provide[
        Container.local_fitbit_repository
    ],
) -> DailyActivityStats:
    report_settings = settings.app_settings.fitbit.activities.get_report(
        activity_type_id=daily_activity.type_id
    )
    goal_distance_km = (
        report_settings.daily_goals.distance_km if report_settings.daily_goals else None
    )

    # No goal set, nothing to do
    if not goal_distance_km:
        return daily_activity

    # We exactly met our goal (unlikely with float numbers, mais bon)
    if daily_activity.sum_distance_km == goal_distance_km:
        return daily_activity

    # We exceeded the goal, add the extra as a credit
    if daily_activity.sum_distance_km > goal_distance_km:
        await local_fitbit_repo.set_credit_distance_km_for_user_and_type_and_date(
            user_lookup=daily_activity.user_lookup,
            type_id=daily_activity.type_id,
            on=daily_activity.date,
            credit_km=daily_activity.sum_distance_km - goal_distance_km,
        )
        return daily_activity

    # We didn't meet the goal, see if we can pull from a secondary activity or our balance
    missing_km = goal_distance_km - daily_activity.sum_distance_km
    if report_settings.streak and report_settings.streak.secondary_activity_type_id:
        # If we have a secondary activity, we don't need to pull as much from our credit balance.
        secondary_daily_activity = await local_fitbit_repo.get_daily_activity_by_user_and_activity_type_and_date(
            user_lookup=daily_activity.user_lookup,
            type_id=report_settings.streak.secondary_activity_type_id,
            on=daily_activity.date,
        )
        if secondary_daily_activity:
            missing_km -= secondary_daily_activity.sum_distance_km
            if missing_km < 0:
                # The secondary activity more than covers for the missing kms, we can return now:
                return daily_activity

    # The secondary activity is't enough, we'll need a debit to not lose our streak
    available_balance = (
        await local_fitbit_repo.get_distance_km_balance_by_user_and_type(
            user_lookup=daily_activity.user_lookup,
            type_id=daily_activity.type_id,
        )
    )

    # Don't have enough in the account to cover the missing kms, too bad, our streak will be lost.
    if available_balance < missing_km:
        return daily_activity

    # Take a debit from our account.
    await local_fitbit_repo.set_debit_distance_km_for_user_and_type_and_date(
        user_lookup=daily_activity.user_lookup,
        type_id=daily_activity.type_id,
        on=daily_activity.date,
        debit_km=missing_km,
    )

    # After the adjustment, get the new activity stats
    return (
        await local_fitbit_repo.get_daily_activity_by_user_and_activity_type_and_date(
            user_lookup=daily_activity.user_lookup,
            type_id=daily_activity.type_id,
            on=daily_activity.date,
        )
    )

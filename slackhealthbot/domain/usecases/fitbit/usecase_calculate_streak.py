import datetime as dt

from dependency_injector.wiring import Provide, inject

from slackhealthbot.containers import Container
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
)
from slackhealthbot.domain.models.activity import (
    DailyActivityStats,
)
from slackhealthbot.settings import Settings, StreakMode


@inject
async def do(
    local_fitbit_repo: LocalFitbitRepository,
    daily_activity: DailyActivityStats,
    end_date: dt.date,
    settings: Settings = Provide[Container.settings],
) -> int | None:
    """
    If we have a goal and we met it at the given date, return the number of consecutive
    days in which the goal was met before, and including this date.

    If we have no goal, return the number of consecutive days, before and including the
    given date, where we had an activity.

    If we have a goal and we didn't meet it at the given date, there's no streak: return None.
    """
    fitbit_userid = daily_activity.fitbit_userid
    report_settings = settings.app_settings.fitbit.activities.get_report(
        activity_type_id=daily_activity.type_id
    )
    goal_distance_km = (
        report_settings.daily_goals.distance_km if report_settings.daily_goals else None
    )
    # If we have a goal and we didn't meet it at the given date, there's no streak: return None.
    if goal_distance_km and daily_activity.sum_distance_km < goal_distance_km:
        return None

    # Return the number of days since the first day in the streak, including the given end_date.
    return await local_fitbit_repo.get_daily_activity_streak_days_count_for_user_and_activity_type(
        fitbit_userid=fitbit_userid,
        type_id=daily_activity.type_id,
        before=end_date,
        min_distance_km=goal_distance_km,
        days_without_activies_break_streak=report_settings.streak_mode
        == StreakMode.strict,
    )

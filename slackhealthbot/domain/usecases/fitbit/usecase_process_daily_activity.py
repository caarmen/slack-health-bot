import datetime as dt

from dependency_injector.wiring import Provide, inject

from slackhealthbot.containers import Container
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
    UserIdentity,
)
from slackhealthbot.domain.models.activity import (
    DailyActivityHistory,
    DailyActivityStats,
    TopActivityStats,
)
from slackhealthbot.domain.usecases.fitbit import usecase_calculate_streak
from slackhealthbot.domain.usecases.slack import usecase_post_daily_activity
from slackhealthbot.settings import Settings

activity_names = {
    55001: "Spinning",
    90013: "Walking",
    90019: "Treadmill",
    90001: "Bike",
}


@inject
async def do(
    daily_activity: DailyActivityStats,
    settings: Settings = Provide[Container.settings],
    local_fitbit_repo: LocalFitbitRepository = Provide[
        Container.local_fitbit_repository
    ],
):
    now = dt.datetime.now(dt.timezone.utc)
    fitbit_userid = daily_activity.fitbit_userid
    streak_distance_km_days = await usecase_calculate_streak.do(
        local_fitbit_repo=local_fitbit_repo,
        daily_activity=daily_activity,
        end_date=now.date(),
    )

    user_identity: UserIdentity = (
        await local_fitbit_repo.get_user_identity_by_fitbit_userid(
            fitbit_userid=fitbit_userid
        )
    )
    previous_daily_activity_stats: DailyActivityStats = (
        await local_fitbit_repo.get_latest_daily_activity_by_user_and_activity_type(
            fitbit_userid=fitbit_userid,
            type_id=daily_activity.type_id,
            before=now.date(),
        )
    )
    all_time_top_daily_activity_stats: TopActivityStats = (
        await local_fitbit_repo.get_top_daily_activity_stats_by_user_and_activity_type(
            fitbit_userid=fitbit_userid,
            type_id=daily_activity.type_id,
        )
    )
    recent_top_daily_activity_stats: TopActivityStats = (
        await local_fitbit_repo.get_top_daily_activity_stats_by_user_and_activity_type(
            fitbit_userid=fitbit_userid,
            type_id=daily_activity.type_id,
            since=now
            - dt.timedelta(days=settings.app_settings.fitbit.activities.history_days),
        )
    )

    history = DailyActivityHistory(
        previous_daily_activity_stats=previous_daily_activity_stats,
        new_daily_activity_stats=daily_activity,
        all_time_top_daily_activity_stats=all_time_top_daily_activity_stats,
        recent_top_daily_activity_stats=recent_top_daily_activity_stats,
        streak_distance_km_days=streak_distance_km_days,
    )

    await usecase_post_daily_activity.do(
        slack_alias=user_identity.slack_alias,
        activity_name=activity_names.get(daily_activity.type_id, "Unknown"),
        history=history,
        record_history_days=settings.app_settings.fitbit.activities.history_days,
    )

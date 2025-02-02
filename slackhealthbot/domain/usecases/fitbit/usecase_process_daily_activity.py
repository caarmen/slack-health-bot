import datetime as dt

from dependency_injector.wiring import Provide, inject
from fastapi import Depends

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
from slackhealthbot.domain.remoterepository.remoteslackrepository import (
    RemoteSlackRepository,
)
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
    local_fitbit_repo: LocalFitbitRepository,
    slack_repo: RemoteSlackRepository,
    daily_activity: DailyActivityStats,
    settings: Settings = Depends(Provide[Container.settings]),
):
    now = dt.datetime.now(dt.timezone.utc)
    fitbit_userid = daily_activity.fitbit_userid
    report_settings = settings.app_settings.fitbit.activities.get_report(
        activity_type_id=daily_activity.type_id
    )
    oldest_daily_activity_stats_in_streak: DailyActivityStats = (
        await local_fitbit_repo.get_oldest_daily_activity_by_user_and_activity_type_in_streak(
            fitbit_userid=fitbit_userid,
            type_id=daily_activity.type_id,
            before=now,
            min_distance_km=(
                report_settings.daily_goals.distance_km
                if report_settings.daily_goals
                else None
            ),
        )
    )
    streak_distance_km_days = (
        (now.date() - oldest_daily_activity_stats_in_streak.date).days + 1
        if oldest_daily_activity_stats_in_streak
        else None
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
        repo=slack_repo,
        slack_alias=user_identity.slack_alias,
        activity_name=activity_names.get(daily_activity.type_id, "Unknown"),
        history=history,
        record_history_days=settings.app_settings.fitbit.activities.history_days,
    )

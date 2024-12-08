import datetime as dt

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
from slackhealthbot.settings import settings

activity_names = {
    55001: "Spinning",
    90013: "Walking",
    90019: "Treadmill",
    90001: "Bike",
}


async def do(
    local_fitbit_repo: LocalFitbitRepository,
    slack_repo: RemoteSlackRepository,
    daily_activity: DailyActivityStats,
):
    now = dt.datetime.now(dt.timezone.utc)
    fitbit_userid = daily_activity.fitbit_userid
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
    )

    await usecase_post_daily_activity.do(
        repo=slack_repo,
        slack_alias=user_identity.slack_alias,
        activity_name=activity_names.get(daily_activity.type_id, "Unknown"),
        history=history,
        record_history_days=settings.app_settings.fitbit.activities.history_days,
    )

import datetime

from dependency_injector.wiring import Provide, inject

from slackhealthbot.containers import Container
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
    UserIdentity,
)
from slackhealthbot.domain.models.activity import (
    ActivityData,
    ActivityHistory,
    TopActivityStats,
)
from slackhealthbot.domain.usecases.fitbit import usecase_get_last_activity
from slackhealthbot.domain.usecases.slack import usecase_post_activity
from slackhealthbot.settings import Settings


@inject
async def do(  # noqa: PLR0913 deal with this later
    fitbit_userid: str,
    when: datetime.datetime,
    settings: Settings = Provide[Container.settings],
    local_fitbit_repo: LocalFitbitRepository = Provide[
        Container.local_fitbit_repository
    ],
) -> ActivityData | None:
    user_identity: UserIdentity = (
        await local_fitbit_repo.get_user_identity_by_fitbit_userid(
            fitbit_userid=fitbit_userid,
        )
    )
    new_activity = await usecase_get_last_activity.do(
        local_repo=local_fitbit_repo,
        fitbit_userid=fitbit_userid,
        when=when,
    )
    if not new_activity:
        return None

    activity_name, new_activity_data = new_activity

    if not await _is_new_valid_activity(
        local_fitbit_repo,
        fitbit_userid=fitbit_userid,
        type_id=new_activity_data.type_id,
        log_id=new_activity_data.log_id,
        settings=settings,
    ):
        return None

    last_activity_data: ActivityData = (
        # Look up the previous activity for this user and type
        # before saving the new activity.
        # Note: if this isn't a realtime activity type, this
        # lookup won't be used. Maybe this can be improved.
        await local_fitbit_repo.get_latest_activity_by_user_and_type(
            fitbit_userid=fitbit_userid,
            type_id=new_activity_data.type_id,
        )
    )

    await local_fitbit_repo.create_activity_for_user(
        fitbit_userid=fitbit_userid,
        activity=new_activity_data,
    )

    report = settings.app_settings.fitbit.activities.get_report(
        activity_type_id=new_activity_data.type_id
    )
    if report is None or not report.realtime:
        # This activity isn't to be posted in realtime to slack.
        # We're done for now.
        return

    all_time_top_activity_stats: TopActivityStats = (
        await local_fitbit_repo.get_top_activity_stats_by_user_and_activity_type(
            fitbit_userid=fitbit_userid,
            type_id=new_activity_data.type_id,
        )
    )
    recent_top_activity_stats: TopActivityStats = (
        await local_fitbit_repo.get_top_activity_stats_by_user_and_activity_type(
            fitbit_userid=fitbit_userid,
            type_id=new_activity_data.type_id,
            since=datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(
                days=settings.app_settings.fitbit.activities.history_days
            ),
        )
    )
    await usecase_post_activity.do(
        slack_alias=user_identity.slack_alias,
        activity_name=activity_name,
        activity_history=ActivityHistory(
            latest_activity_data=last_activity_data,
            new_activity_data=new_activity_data,
            all_time_top_activity_data=all_time_top_activity_stats,
            recent_top_activity_data=recent_top_activity_stats,
        ),
        record_history_days=settings.app_settings.fitbit.activities.history_days,
    )

    return new_activity_data


async def _is_new_valid_activity(
    repo: LocalFitbitRepository,
    fitbit_userid: str,
    type_id: int,
    log_id: int,
    settings: Settings,
) -> bool:
    return settings.app_settings.fitbit.activities.get_activity_type(
        id=type_id
    ) and not await repo.get_activity_by_user_and_log_id(
        fitbit_userid=fitbit_userid,
        log_id=log_id,
    )

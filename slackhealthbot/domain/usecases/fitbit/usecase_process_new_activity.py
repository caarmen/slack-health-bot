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
from slackhealthbot.domain.remoterepository.remotefitbitrepository import (
    RemoteFitbitRepository,
)
from slackhealthbot.domain.usecases.slack import usecase_post_activity
from slackhealthbot.settings import Settings


@inject
async def do(  # noqa: PLR0913 deal with this later
    fitbit_userid: str,
    when: datetime.date,
    settings: Settings = Provide[Container.settings],
    local_fitbit_repo: LocalFitbitRepository = Provide[
        Container.local_fitbit_repository
    ],
    remote_fitbit_repo: RemoteFitbitRepository = Provide[
        Container.remote_fitbit_repository
    ],
) -> list[ActivityData]:
    user_identity: UserIdentity = (
        await local_fitbit_repo.get_user_identity_by_fitbit_userid(
            fitbit_userid=fitbit_userid,
        )
    )
    user = await local_fitbit_repo.get_user_by_fitbit_userid(
        fitbit_userid=fitbit_userid,
    )
    activities = await remote_fitbit_repo.get_activities_for_date(
        oauth_fields=user.oauth_data,
        when=when,
    )
    if not activities:
        return []

    now = datetime.datetime.now(datetime.timezone.utc)
    report_history_days = settings.app_settings.fitbit.activities.history_days
    recent_since = now - datetime.timedelta(days=report_history_days)
    processed_activities: list[ActivityData] = []

    for activity_name, new_activity_data in activities:
        if not settings.app_settings.fitbit.activities.get_activity_type(
            id=new_activity_data.type_id
        ):
            continue

        created = await local_fitbit_repo.upsert_activity_for_user(
            fitbit_userid=fitbit_userid,
            activity=new_activity_data,
        )
        if not created:
            continue

        report = settings.app_settings.fitbit.activities.get_report(
            activity_type_id=new_activity_data.type_id
        )
        if report is None or not report.realtime:
            # This activity isn't to be posted in realtime to slack.
            continue

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
                since=recent_since,
            )
        )
        await usecase_post_activity.do(
            slack_alias=user_identity.slack_alias,
            activity_name=activity_name,
            activity_history=ActivityHistory(
                new_activity_data=new_activity_data,
                all_time_top_activity_data=all_time_top_activity_stats,
                recent_top_activity_data=recent_top_activity_stats,
            ),
            record_history_days=report_history_days,
        )
        processed_activities.append(new_activity_data)

    return processed_activities

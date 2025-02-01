import datetime as dt

from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
)
from slackhealthbot.domain.models.activity import DailyActivityStats
from slackhealthbot.domain.remoterepository.remoteslackrepository import (
    RemoteSlackRepository,
)
from slackhealthbot.domain.usecases.fitbit import usecase_process_daily_activity


async def do(
    local_fitbit_repo: LocalFitbitRepository,
    type_ids: set[int],
    slack_repo: RemoteSlackRepository,
):
    list_daily_activities: list[DailyActivityStats] = (
        await local_fitbit_repo.get_daily_activities_by_type(
            type_ids=type_ids,
            when=dt.datetime.now(dt.timezone.utc).date(),
        )
    )
    for daily_activity in list_daily_activities:
        await usecase_process_daily_activity.do(
            local_fitbit_repo=local_fitbit_repo,
            slack_repo=slack_repo,
            daily_activity=daily_activity,
        )

import datetime

from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
    UserIdentity,
)
from slackhealthbot.domain.models.sleep import SleepData
from slackhealthbot.domain.remoterepository.remotefitbitrepository import (
    RemoteFitbitRepository,
)
from slackhealthbot.domain.usecases.fitbit import usecase_get_last_sleep
from slackhealthbot.domain.usecases.slack import usecase_post_sleep


async def do(
    local_fitbit_repo: LocalFitbitRepository,
    remote_fitbit_repo: RemoteFitbitRepository,
    fitbit_userid: str,
    when: datetime.date,
) -> SleepData | None:
    user_identity: UserIdentity = (
        await local_fitbit_repo.get_user_identity_by_fitbit_userid(
            fitbit_userid=fitbit_userid,
        )
    )
    last_sleep_data: SleepData = await local_fitbit_repo.get_sleep_by_fitbit_userid(
        fitbit_userid=fitbit_userid,
    )
    new_sleep_data: SleepData = await usecase_get_last_sleep.do(
        local_repo=local_fitbit_repo,
        remote_repo=remote_fitbit_repo,
        fitbit_userid=fitbit_userid,
        when=when,
    )
    if not new_sleep_data:
        return None
    await local_fitbit_repo.update_sleep_for_user(
        fitbit_userid=fitbit_userid,
        sleep=new_sleep_data,
    )
    await usecase_post_sleep.do(
        slack_alias=user_identity.slack_alias,
        new_sleep_data=new_sleep_data,
        last_sleep_data=last_sleep_data,
    )
    return new_sleep_data

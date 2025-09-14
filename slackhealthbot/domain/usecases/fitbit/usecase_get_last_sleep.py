import datetime

from dependency_injector.wiring import Provide, inject

from slackhealthbot.containers import Container
from slackhealthbot.core.models import OAuthFields
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
)
from slackhealthbot.domain.models.sleep import SleepData
from slackhealthbot.domain.remoterepository.remotefitbitrepository import (
    RemoteFitbitRepository,
)


@inject
async def do(
    fitbit_userid: str,
    when: datetime.date,
    local_repo: LocalFitbitRepository = Provide[Container.local_fitbit_repository],
    remote_repo: RemoteFitbitRepository = Provide[Container.remote_fitbit_repository],
) -> SleepData | None:
    oauth_data: OAuthFields = await local_repo.get_oauth_data_by_fitbit_userid(
        fitbit_userid=fitbit_userid,
    )
    return await remote_repo.get_sleep(
        oauth_fields=oauth_data,
        when=when,
    )

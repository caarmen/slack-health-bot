import datetime

from dependency_injector.wiring import Provide, inject

from slackhealthbot.containers import Container
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
    User,
)
from slackhealthbot.domain.models.activity import ActivityData
from slackhealthbot.domain.remoterepository.remotefitbitrepository import (
    RemoteFitbitRepository,
)


@inject
async def do(
    local_repo: LocalFitbitRepository,
    fitbit_userid: str,
    when: datetime.datetime,
    remote_repo: RemoteFitbitRepository = Provide[Container.remote_fitbit_repository],
) -> tuple[str, ActivityData] | None:
    user: User = await local_repo.get_user_by_fitbit_userid(
        fitbit_userid=fitbit_userid,
    )
    return await remote_repo.get_activity(
        oauth_fields=user.oauth_data,
        when=when,
    )

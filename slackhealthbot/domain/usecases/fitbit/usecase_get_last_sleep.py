import datetime

from dependency_injector.wiring import Provide, inject

from slackhealthbot.containers import Container
from slackhealthbot.core.models import OAuthFields
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
    User,
)
from slackhealthbot.domain.models.sleep import SleepData
from slackhealthbot.domain.models.users import UserLookup
from slackhealthbot.domain.remoterepository.remotefitbitrepository import (
    RemoteFitbitRepository,
)
from slackhealthbot.domain.remoterepository.remotegooglerepository import (
    RemoteGoogleRepository,
)


@inject
async def do(
    user_lookup: UserLookup,
    when: datetime.date,
    local_repo: LocalFitbitRepository = Provide[Container.local_fitbit_repository],
    remote_fitbit_repo: RemoteFitbitRepository = Provide[
        Container.remote_fitbit_repository
    ],
    remote_google_repo: RemoteGoogleRepository = Provide[
        Container.remote_google_repository
    ],
) -> SleepData | None:
    oauth_data: OAuthFields = await local_repo.get_oauth_data_by_user_lookup(
        user_lookup
    )
    user: User = await local_repo.get_user_by_lookup(user_lookup)
    if user.identity.health_user_id is not None:
        return await remote_google_repo.get_sleep(
            oauth_fields=oauth_data,
            when=when,
        )
    return await remote_fitbit_repo.get_sleep(
        oauth_fields=oauth_data,
        when=when,
    )

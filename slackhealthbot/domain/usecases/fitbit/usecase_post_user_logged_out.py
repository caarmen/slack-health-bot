from dependency_injector.wiring import Provide, inject

from slackhealthbot.containers import Container
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
    UserIdentity,
)
from slackhealthbot.domain.models.users import HealthUserLookup, UserLookup
from slackhealthbot.domain.usecases.slack import (
    usecase_post_user_logged_out as slack_usecase_post_user_logged_out,
)


@inject
async def do(
    user_lookup: UserLookup,
    fitbit_repo: LocalFitbitRepository = Provide[Container.local_fitbit_repository],
):
    service = "google" if isinstance(user_lookup, HealthUserLookup) else "fitbit"
    user_identity: UserIdentity = await fitbit_repo.get_user_identity(user_lookup)
    await slack_usecase_post_user_logged_out.do(
        slack_alias=user_identity.slack_alias,
        service=service,
    )

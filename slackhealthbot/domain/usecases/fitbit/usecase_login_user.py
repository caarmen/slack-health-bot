from typing import Any

from dependency_injector.wiring import Provide, inject

from slackhealthbot.containers import Container
from slackhealthbot.core.models import OAuthFields
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
    User,
    UserIdentity,
)
from slackhealthbot.domain.remoterepository.remotefitbitrepository import (
    RemoteFitbitRepository,
)


@inject
async def do(
    slack_alias: str,
    token: dict[str, Any],
    local_repo: LocalFitbitRepository = Provide[Container.local_fitbit_repository],
    remote_repo: RemoteFitbitRepository = Provide[Container.remote_fitbit_repository],
):
    user: User = await _upsert_user(local_repo, remote_repo, slack_alias, token)
    await remote_repo.subscribe(oauth_fields=user.oauth_data)


async def _upsert_user(
    local_repo: LocalFitbitRepository,
    remote_repo: RemoteFitbitRepository,
    slack_alias: str,
    token: dict[str, Any],
) -> User:
    oauth_fields: OAuthFields = remote_repo.parse_oauth_fields(token)
    user_identity: UserIdentity = await local_repo.get_user_identity_by_fitbit_userid(
        fitbit_userid=oauth_fields.oauth_userid
    )
    if not user_identity:
        return await local_repo.create_user(
            slack_alias=slack_alias,
            fitbit_userid=oauth_fields.oauth_userid,
            oauth_data=oauth_fields,
        )
    else:
        await local_repo.update_oauth_data(
            fitbit_userid=oauth_fields.oauth_userid,
            oauth_data=oauth_fields,
        )
    return await local_repo.get_user_by_fitbit_userid(
        fitbit_userid=oauth_fields.oauth_userid,
    )

from typing import Any

from dependency_injector.wiring import Provide, inject

from slackhealthbot.containers import Container
from slackhealthbot.core.models import OAuthFields
from slackhealthbot.domain.localrepository.localwithingsrepository import (
    LocalWithingsRepository,
    User,
    UserIdentity,
)
from slackhealthbot.domain.remoterepository.remotewithingsrepository import (
    RemoteWithingsRepository,
)


@inject
async def do(
    local_repo: LocalWithingsRepository,
    slack_alias: str,
    token: dict[str, Any],
    remote_repo: RemoteWithingsRepository = Provide[
        Container.remote_withings_repository
    ],
):
    user: User = await _upsert_user(local_repo, remote_repo, slack_alias, token)
    await remote_repo.subscribe(user.oauth_data)


async def _upsert_user(
    local_repo: LocalWithingsRepository,
    remote_repo: RemoteWithingsRepository,
    slack_alias: str,
    token: dict[str, Any],
) -> User:
    oauth_fields: OAuthFields = remote_repo.parse_oauth_fields(token)
    user_identity: UserIdentity = await local_repo.get_user_identity_by_withings_userid(
        withings_userid=oauth_fields.oauth_userid
    )
    if not user_identity:
        return await local_repo.create_user(
            slack_alias=slack_alias,
            withings_userid=oauth_fields.oauth_userid,
            oauth_data=oauth_fields,
        )
    else:
        await local_repo.update_oauth_data(
            withings_userid=oauth_fields.oauth_userid,
            oauth_data=oauth_fields,
        )
    return await local_repo.get_user_by_withings_userid(
        withings_userid=oauth_fields.oauth_userid,
    )

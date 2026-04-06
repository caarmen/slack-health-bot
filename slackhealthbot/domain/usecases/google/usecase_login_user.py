from typing import Any

from dependency_injector.wiring import Provide, inject

from slackhealthbot.containers import Container
from slackhealthbot.core.models import OAuthFields
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
    User,
    UserIdentity,
)
from slackhealthbot.domain.models.users import FitbitUserLookup, HealthUserLookup
from slackhealthbot.domain.remoterepository.remotegooglerepository import (
    HealthIds,
    RemoteGoogleRepository,
)


@inject
async def do(
    slack_alias: str,
    token: dict[str, Any],
    local_repo: LocalFitbitRepository = Provide[Container.local_fitbit_repository],
    remote_repo: RemoteGoogleRepository = Provide[Container.remote_google_repository],
):
    await _upsert_user(local_repo, remote_repo, slack_alias, token)


async def _upsert_user(
    local_repo: LocalFitbitRepository,
    remote_repo: RemoteGoogleRepository,
    slack_alias: str,
    token: dict[str, Any],
) -> User:
    oauth_fields: OAuthFields = remote_repo.parse_oauth_fields(token)
    health_ids: HealthIds = await remote_repo.get_identity(oauth_fields)
    user_identity: UserIdentity = None
    if health_ids.fitbit_user_id:
        user_identity = await local_repo.get_user_identity(
            FitbitUserLookup(user_id=health_ids.fitbit_user_id),
        )

    # Matching legacy fitbit user.
    # Update its oauth fields, looking up by their legacy fitbit user id
    # and then updating the oauth_userid to now be the google oauth user id.
    if user_identity:
        await local_repo.update_oauth_data(
            oauth_userid=health_ids.fitbit_user_id,
            oauth_data=oauth_fields,
        )

    # No matching legacy fitbit user.
    # See if we have a google-only user.
    else:
        user_identity = await local_repo.get_user_identity(
            HealthUserLookup(user_id=health_ids.health_user_id)
        )
        # Found existing google-only user.
        # Update their oauth info (their oauth_userid won't change)
        if user_identity:
            await local_repo.update_oauth_data(
                oauth_userid=oauth_fields.oauth_userid,
                oauth_data=oauth_fields,
            )

    # Found either legacy fitbit or google-only user.
    # Update their lookup fields.
    if user_identity:
        await local_repo.update_user_ids(
            oauth_userid=oauth_fields.oauth_userid,
            fitbit_user_id=health_ids.fitbit_user_id,
            health_user_id=health_ids.health_user_id,
        )

    # No matching legacy fitbit user OR google user.
    # Create the user.
    else:
        return await local_repo.create_user(
            slack_alias=slack_alias,
            fitbit_user_id=health_ids.fitbit_user_id,
            health_user_id=health_ids.health_user_id,
            oauth_data=oauth_fields,
        )

    return await local_repo.get_user_identity(
        HealthUserLookup(user_id=health_ids.health_user_id)
    )

from typing import Any, Callable

from dependency_injector.wiring import Provide, inject

from slackhealthbot.containers import Container
from slackhealthbot.core.models import OAuthFields
from slackhealthbot.domain.localrepository.localwithingsrepository import (
    LocalWithingsRepository,
)
from slackhealthbot.domain.remoterepository.remotewithingsrepository import (
    RemoteWithingsRepository,
)


class UpdateTokenUseCase(Callable):

    @inject
    def __init__(
        self,
        remote_repo: RemoteWithingsRepository = Provide[
            Container.remote_withings_repository
        ],
    ):
        self.remote_repo = remote_repo

    @inject
    async def __call__(
        self,
        token: dict[str, Any],
        local_repo: LocalWithingsRepository = Provide[
            Container.local_withings_repository
        ],
        **kwargs,
    ):
        oauth_fields: OAuthFields = self.remote_repo.parse_oauth_fields(token)
        await local_repo.update_oauth_data(
            withings_userid=oauth_fields.oauth_userid,
            oauth_data=oauth_fields,
        )

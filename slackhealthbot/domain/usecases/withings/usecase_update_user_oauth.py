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
        request_context_withings_repository: Callable[[], LocalWithingsRepository],
        remote_repo: RemoteWithingsRepository = Provide[
            Container.remote_withings_repository
        ],
    ):
        self.request_context_withings_repository = request_context_withings_repository
        self.remote_repo = remote_repo

    async def __call__(self, token: dict[str, Any], **kwargs):
        local_repo: LocalWithingsRepository = self.request_context_withings_repository()
        oauth_fields: OAuthFields = self.remote_repo.parse_oauth_fields(token)
        await local_repo.update_oauth_data(
            withings_userid=oauth_fields.oauth_userid,
            oauth_data=oauth_fields,
        )

from typing import Any, Callable

from dependency_injector.wiring import Provide, inject

from slackhealthbot.containers import Container
from slackhealthbot.core.models import OAuthFields
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
)
from slackhealthbot.domain.remoterepository.remotefitbitrepository import (
    RemoteFitbitRepository,
)


class UpdateTokenUseCase(Callable):

    @inject
    def __init__(
        self,
        request_context_fitbit_repository: Callable[[], LocalFitbitRepository],
        remote_repo: RemoteFitbitRepository = Provide[
            Container.remote_fitbit_repository
        ],
    ):
        self.request_context_fitbit_repository = request_context_fitbit_repository
        self.remote_repo = remote_repo

    async def __call__(self, token: dict[str, Any], **kwargs):
        local_repo: LocalFitbitRepository = self.request_context_fitbit_repository()
        oauth_fields: OAuthFields = self.remote_repo.parse_oauth_fields(token)
        await local_repo.update_oauth_data(
            fitbit_userid=oauth_fields.oauth_userid,
            oauth_data=oauth_fields,
        )

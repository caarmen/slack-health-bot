import datetime as dt
from typing import Any, Callable

from dependency_injector.wiring import Provide, inject

from slackhealthbot.containers import Container
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
)
from slackhealthbot.domain.remoterepository.remotegooglerepository import (
    RemoteGoogleRepository,
)


class UpdateTokenUseCase(Callable):
    @inject
    def __init__(
        self,
        remote_repo: RemoteGoogleRepository = Provide[
            Container.remote_google_repository
        ],
    ):
        self.remote_repo = remote_repo

    @inject
    async def __call__(
        self,
        token: dict[str, Any],
        refresh_token: str | None = None,
        local_repo: LocalFitbitRepository = Provide[Container.local_fitbit_repository],
        **_kwargs,
    ):
        # https://docs.authlib.org/en/stable/client/frameworks.html#auto-update-token
        await local_repo.update_token_by_refresh_token(
            refresh_token=refresh_token,
            new_access_token=token["access_token"],
            new_expiration_date=dt.datetime.now(dt.timezone.utc)
            + dt.timedelta(seconds=int(token["expires_in"]))
            - dt.timedelta(minutes=5),
        )

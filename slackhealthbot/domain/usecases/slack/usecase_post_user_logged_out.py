from dependency_injector.wiring import Provide, inject
from fastapi import Depends

from slackhealthbot.containers import Container
from slackhealthbot.domain.remoterepository.remoteslackrepository import (
    RemoteSlackRepository,
)
from slackhealthbot.settings import Settings


@inject
async def do(
    repo: RemoteSlackRepository,
    slack_alias: str,
    service: str,
    settings: Settings = Depends(Provide[Container.settings]),
):
    message = f"""
Oh no <@{slack_alias}>, looks like you were logged out of {service}! 😳.
You'll need to log in again to get your reports:
{settings.app_settings.server_url}v1/{service}-authorization/{slack_alias}
"""
    await repo.post_message(message)

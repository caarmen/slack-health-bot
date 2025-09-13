import logging

from dependency_injector.wiring import Provide, inject

from slackhealthbot.containers import Container
from slackhealthbot.core.models import OAuthFields
from slackhealthbot.oauth import requests
from slackhealthbot.settings import Settings


@inject
async def subscribe(
    oauth_token: OAuthFields,
    settings: Settings = Provide[Container.settings],
):
    for collectionPath in ["sleep", "activities"]:
        response = await requests.post(
            provider=settings.fitbit_oauth_settings.name,
            token=oauth_token,
            url=f"{settings.fitbit_oauth_settings.base_url}1/user/-/{collectionPath}/apiSubscriptions/{oauth_token.oauth_userid}-{collectionPath}.json",
        )
        logging.info(
            f"Fitbit {collectionPath} subscription response: {response.json()}"
        )

import logging

from slackhealthbot.core.exceptions import UserLoggedOutException
from slackhealthbot.core.models import OAuthFields
from slackhealthbot.oauth import requests
from slackhealthbot.settings import Settings


async def subscribe(
    oauth_token: OAuthFields,
    settings: Settings,
):
    callbackurl = (
        f"{settings.withings_oauth_settings.callback_url}withings-notification-webhook/"
    )
    # https://developer.withings.com/api-reference#tag/notify/operation/notify-subscribe
    try:
        response = await requests.post(
            provider=settings.withings_oauth_settings.name,
            token=oauth_token,
            url=f"{settings.withings_oauth_settings.base_url}notify",
            data={
                "action": "subscribe",
                "callbackurl": callbackurl,
                "appli": 1,
            },
        )
        logging.info(f"Withings subscription response: {response.json()}")
    except UserLoggedOutException:
        logging.warning(
            "Error subscribing. This may be normal in a debug environment (http on localhost)"
        )

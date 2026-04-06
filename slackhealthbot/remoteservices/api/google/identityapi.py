import logging

from pydantic import BaseModel

from slackhealthbot.core.models import OAuthFields
from slackhealthbot.oauth import requests
from slackhealthbot.settings import Settings


class Identity(BaseModel):
    legacyUserId: str | None = None
    healthUserId: str


async def get_identity(
    oauth_token: OAuthFields,
    settings: Settings,
) -> Identity:
    """
    https://developers.google.com/health/reference/rest/v4/users/getIdentity
    """
    response = await requests.get(
        provider=settings.google_oauth_settings.name,
        token=oauth_token,
        url="/v4/users/me/identity",
    )
    logging.info(f"Google health identity response: {response.json()}")
    return Identity.model_validate(response.json())

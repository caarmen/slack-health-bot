import logging
from typing import Any, Callable

from authlib.integrations.httpx_client.oauth2_client import AsyncOAuth2Client
from fastapi import status

from slackhealthbot.core.exceptions import UserLoggedOutException
from slackhealthbot.oauth.config import oauth
from slackhealthbot.settings import fitbit_oauth_settings as settings


def fitbit_compliance_fix(session: AsyncOAuth2Client):
    def _fix_access_token_response(resp):
        logging.info(f"Token response {resp}")
        if is_auth_failure(resp):
            raise UserLoggedOutException
        data = resp.json()
        data["userid"] = data["user_id"]
        resp.json = lambda: data
        return resp

    session.register_compliance_hook(
        "refresh_token_response", _fix_access_token_response
    )
    session.register_compliance_hook(
        "access_token_response", _fix_access_token_response
    )


def is_auth_failure(response) -> bool:
    return response.status_code != status.HTTP_200_OK


def configure(update_token_callback: Callable[[dict[str, Any]], None]):
    oauth.register(
        name=settings.name,
        api_base_url=settings.base_url,
        authorize_url="https://www.fitbit.com/oauth2/authorize",
        access_token_url=f"{settings.base_url}oauth2/token",
        authorize_params={"scope": " ".join(settings.oauth_scopes)},
        compliance_fix=fitbit_compliance_fix,
        update_token=update_token_callback,
        token_endpoint_auth_method="client_secret_basic",
        client_kwargs={
            "code_challenge_method": "S256",
            "is_auth_failure": is_auth_failure,
        },
    )

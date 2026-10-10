import logging
from typing import Any, Callable, Coroutine
from urllib import parse

import httpx
from authlib.integrations.httpx_client.oauth2_client import AsyncOAuth2Client
from dependency_injector.wiring import Provide, inject
from fastapi import status

from slackhealthbot.containers import Container
from slackhealthbot.oauth.config import oauth
from slackhealthbot.settings import Settings


@inject
def google_compliance_fix(
    session: AsyncOAuth2Client,
    settings: Settings = Provide[Container.settings],
):
    # https://developers.google.com/identity/protocols/oauth2/web-server#httprest_8
    def _fix_refresh_token_request(url, headers, body):
        fields_dict = dict(parse.parse_qsl(body))
        # Remove scope for refresh token
        fields_dict.pop("scope")
        # Add client_id for refresh token
        fields_dict["client_id"] = settings.secret_settings.google_client_id
        new_body = parse.urlencode(fields_dict)
        return url, headers, new_body

    session.register_compliance_hook(
        "refresh_token_request", _fix_refresh_token_request
    )


def is_auth_failure(response) -> bool:
    if response.status_code == status.HTTP_401_UNAUTHORIZED:
        logging.warning(f"Auth failure {response.json()}")
        return True
    return False


@inject
def configure(
    update_token_callback: Callable[[dict[str, Any]], Coroutine],
    settings: Settings = Provide[Container.settings],
):
    oauth.register(
        api_base_url=settings.google_oauth_settings.base_url,
        name=settings.google_oauth_settings.name,
        server_metadata_url=settings.google_oauth_settings.oidc_url,
        client_kwargs={
            "scope": " ".join(settings.google_oauth_settings.oauth_scopes),
            "timeout": settings.app_settings.request_timeout_s,
            "transport": httpx.AsyncHTTPTransport(
                retries=settings.app_settings.request_retries
            ),
            "is_auth_failure": is_auth_failure,
        },
        authorize_params={
            "access_type": "offline",
            "prompt": "select_account consent",
        },
        update_token=update_token_callback,
        compliance_fix=google_compliance_fix,
    )

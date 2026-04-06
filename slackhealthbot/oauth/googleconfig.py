import logging
from typing import Any, Callable, Coroutine

import httpx
from dependency_injector.wiring import Provide, inject
from fastapi import status

from slackhealthbot.containers import Container
from slackhealthbot.oauth.config import oauth
from slackhealthbot.settings import Settings


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
    )

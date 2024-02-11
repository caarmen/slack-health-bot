import logging
from typing import Any, Callable

from authlib.common.urls import add_params_to_qs
from authlib.integrations.httpx_client.oauth2_client import AsyncOAuth2Client

from slackhealthbot.core.exceptions import UserLoggedOutException
from slackhealthbot.oauth.config import oauth
from slackhealthbot.settings import withings_oauth_settings as settings

ACCESS_TOKEN_EXTRA_PARAMS = {
    "action": "requesttoken",
}


def withings_compliance_fix(session: AsyncOAuth2Client):
    def _fix_refresh_token_request(url, headers, body):
        body = add_params_to_qs(body, ACCESS_TOKEN_EXTRA_PARAMS)
        return url, headers, body

    def _fix_access_token_response(resp):
        logging.info(f"Token response {resp}")
        # https://developer.withings.com/api-reference/#section/Response-status
        if is_auth_failure(resp):
            resp.status_code = 400
            raise UserLoggedOutException
        data = resp.json()
        resp.json = lambda: data["body"]
        return resp

    session.register_compliance_hook(
        "refresh_token_request", _fix_refresh_token_request
    )
    session.register_compliance_hook(
        "refresh_token_response", _fix_access_token_response
    )
    session.register_compliance_hook(
        "access_token_response", _fix_access_token_response
    )


def is_auth_failure(response) -> bool:
    status = response.json()["status"]
    # https://developer.withings.com/api-reference/#tag/response_status
    if status != 0:
        logging.warning(f"Auth failure {response.json()}")
        return True
    return False


def configure(update_token_callback: Callable[[dict[str, Any]], None]):
    oauth.register(
        name=settings.name,
        api_base_url=settings.base_url,
        authorize_url="https://account.withings.com/oauth2_user/authorize2",
        access_token_url=f"{settings.base_url}v2/oauth2",
        access_token_params=ACCESS_TOKEN_EXTRA_PARAMS,
        authorize_params={"scope": ",".join(settings.oauth_scopes)},
        compliance_fix=withings_compliance_fix,
        update_token=update_token_callback,
        token_endpoint_auth_method="client_secret_post",
        client_kwargs={
            "is_auth_failure": is_auth_failure,
        },
    )

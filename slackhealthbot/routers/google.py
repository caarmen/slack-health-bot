from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Request

from slackhealthbot.containers import Container
from slackhealthbot.domain.usecases.google import (
    usecase_login_user,
)
from slackhealthbot.oauth.config import oauth
from slackhealthbot.routers.dependencies import (
    templates,
)
from slackhealthbot.settings import Settings

router = APIRouter()


@router.get("/v1/google-authorization/{slack_alias}")
@inject
async def get_google_authorization(
    slack_alias: str,
    request: Request,
    settings: Settings = Provide[Container.settings],
):
    request.session["slack_alias"] = slack_alias
    return await oauth.create_client(
        settings.google_oauth_settings.name
    ).authorize_redirect(
        request,
        redirect_uri=settings.google_oauth_settings.redirect_uri,
    )


@router.get("/google-oauth-webhook")
@inject
async def google_oauth_webhook(
    request: Request,
    settings: Settings = Provide[Container.settings],
):
    token: dict = await oauth.create_client(
        settings.google_oauth_settings.name
    ).authorize_access_token(request)
    await usecase_login_user.do(
        token=token,
        slack_alias=request.session.pop("slack_alias"),
    )
    return templates.TemplateResponse(
        request=request, name="login_complete.html", context={"provider": "google"}
    )

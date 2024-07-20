import logging

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel

from slackhealthbot.core.exceptions import UnknownUserException, UserLoggedOutException
from slackhealthbot.domain.localrepository.localwithingsrepository import (
    LocalWithingsRepository,
)
from slackhealthbot.domain.remoterepository.remoteslackrepository import (
    RemoteSlackRepository,
)
from slackhealthbot.domain.remoterepository.remotewithingsrepository import (
    RemoteWithingsRepository,
)
from slackhealthbot.domain.usecases.withings import (
    usecase_login_user,
    usecase_post_user_logged_out,
    usecase_process_new_weight,
)
from slackhealthbot.domain.usecases.withings.usecase_process_new_weight import (
    NewWeightParameters,
)
from slackhealthbot.oauth.config import oauth
from slackhealthbot.routers.dependencies import (
    get_local_withings_repository,
    get_remote_withings_repository,
    get_slack_repository,
    templates,
)
from slackhealthbot.settings import withings_oauth_settings as settings

router = APIRouter()


@router.head("/withings-oauth-webhook/")
def validate_withings_oauth_webhook():
    return Response()


@router.head("/withings-notification-webhook/")
def validate_withings_notification_webhook():
    return Response()


@router.get("/withings-oauth-webhook/")
async def withings_oauth_webhook(
    request: Request,
    local_repo: LocalWithingsRepository = Depends(get_local_withings_repository),
    remote_repo: RemoteWithingsRepository = Depends(get_remote_withings_repository),
):
    token: dict = await oauth.create_client(settings.name).authorize_access_token(
        request
    )
    await usecase_login_user.do(
        local_repo=local_repo,
        remote_repo=remote_repo,
        token=token,
        slack_alias=request.session.pop("slack_alias"),
    )
    return templates.TemplateResponse(
        request=request, name="login_complete.html", context={"provider": "withings"}
    )


@router.get("/v1/withings-authorization/{slack_alias}")
async def get_withings_authorization(slack_alias: str, request: Request):
    request.session["slack_alias"] = slack_alias
    return await oauth.create_client(settings.name).authorize_redirect(
        request, redirect_uri=settings.redirect_uri
    )


last_processed_withings_notification_per_user = {}


class WithingsNotification(BaseModel):
    userid: str
    startdate: int
    enddate: int


async def parse_notification(request: Request):
    return WithingsNotification(**(await request.form()))


@router.post("/withings-notification-webhook/")
async def withings_notification_webhook(
    notification: WithingsNotification = Depends(parse_notification),
    withings_local_repo: LocalWithingsRepository = Depends(
        get_local_withings_repository
    ),
    withings_remote_repo: RemoteWithingsRepository = Depends(
        get_remote_withings_repository
    ),
    slack_repo: RemoteSlackRepository = Depends(get_slack_repository),
):
    logging.info(
        "withings_notification_webhook: "
        + f"userid={notification.userid}, startdate={notification.startdate}, enddate={notification.enddate}"
    )
    if last_processed_withings_notification_per_user.get(notification.userid, None) != (
        notification.startdate,
        notification.enddate,
    ):
        try:
            await usecase_process_new_weight.do(
                local_withings_repo=withings_local_repo,
                remote_withings_repo=withings_remote_repo,
                slack_repo=slack_repo,
                new_weight_parameters=NewWeightParameters(
                    withings_userid=notification.userid,
                    startdate=notification.startdate,
                    enddate=notification.enddate,
                ),
            )
            last_processed_withings_notification_per_user[notification.userid] = (
                notification.startdate,
                notification.enddate,
            )
        except UserLoggedOutException:
            await usecase_post_user_logged_out.do(
                withings_repo=withings_local_repo,
                slack_repo=slack_repo,
                withings_userid=notification.userid,
            )
        except UnknownUserException:
            logging.info("withings_notification_webhook: unknown user")
            return Response(status_code=status.HTTP_404_NOT_FOUND)
    else:
        logging.info("Ignoring duplicate withings notification")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

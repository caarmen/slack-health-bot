import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from slackhealthbot.core.exceptions import UserLoggedOutException
from slackhealthbot.domain.withings import (
    usecase_login_user,
    usecase_post_user_logged_out,
    usecase_process_new_weight,
)
from slackhealthbot.routers.dependencies import get_db, templates
from slackhealthbot.services.oauth.config import oauth
from slackhealthbot.settings import withings_oauth_settings as settings

router = APIRouter()


@router.head("/withings-oauth-webhook/")
def validate_withings_oauth_webhook():
    return Response()


@router.head("/withings-notification-webhook/")
def validate_withings_notification_webhook():
    return Response()


@router.get("/withings-oauth-webhook/")
async def withings_oauth_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    token: dict = await oauth.create_client(settings.name).authorize_access_token(
        request
    )
    await usecase_login_user.do(
        db=db, token=token, slack_alias=request.session.pop("slack_alias")
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


@router.post("/withings-notification-webhook/")
async def withings_notification_webhook(
    userid: Annotated[str, Form()],
    startdate: Annotated[int, Form()],
    enddate: Annotated[int, Form()],
    db: AsyncSession = Depends(get_db),
):
    logging.info(
        "withings_notification_webhook: "
        + f"userid={userid}, startdate={startdate}, enddate={enddate}"
    )
    if last_processed_withings_notification_per_user.get(userid, None) != (
        startdate,
        enddate,
    ):
        try:
            await usecase_process_new_weight.do(
                db,
                withings_userid=userid,
                startdate=startdate,
                enddate=enddate,
            )
            last_processed_withings_notification_per_user[userid] = (
                startdate,
                enddate,
            )
        except UserLoggedOutException:
            await usecase_post_user_logged_out.do(
                db=db,
                withings_userid=userid,
            )
    else:
        logging.info("Ignoring duplicate withings notification")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

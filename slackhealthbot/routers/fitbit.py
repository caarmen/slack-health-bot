import datetime
import logging
from asyncio import Lock

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel

from slackhealthbot.containers import Container
from slackhealthbot.core.exceptions import UnknownUserException, UserLoggedOutException
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
)
from slackhealthbot.domain.usecases.fitbit import (
    usecase_login_user,
    usecase_post_user_logged_out,
    usecase_process_new_activity,
    usecase_process_new_sleep,
)
from slackhealthbot.oauth.config import oauth
from slackhealthbot.routers.dependencies import (
    get_local_fitbit_repository,
    templates,
)
from slackhealthbot.settings import Settings

router = APIRouter()


@router.get("/v1/fitbit-authorization/{slack_alias}")
@inject
async def get_fitbit_authorization(
    slack_alias: str,
    request: Request,
    settings: Settings = Depends(Provide[Container.settings]),
):
    request.session["slack_alias"] = slack_alias
    return await oauth.create_client(
        settings.fitbit_oauth_settings.name
    ).authorize_redirect(request)


@router.get("/fitbit-notification-webhook/")
@inject
def validate_fitbit_notification_webhook(
    verify: str | None = None,
    settings: Settings = Depends(Provide[Container.settings]),
):
    # See the fitbit verification doc:
    # https://dev.fitbit.com/build/reference/web-api/developer-guide/using-subscriptions/#Verifying-a-Subscriber
    if verify == settings.fitbit_oauth_settings.subscriber_verification_code:
        return Response(status_code=204)
    return Response(status_code=404)


@router.get("/fitbit-oauth-webhook/")
@inject
async def fitbit_oauth_webhook(
    request: Request,
    local_repo: LocalFitbitRepository = Depends(get_local_fitbit_repository),
    settings: Settings = Depends(Provide[Container.settings]),
):
    token: dict = await oauth.create_client(
        settings.fitbit_oauth_settings.name
    ).authorize_access_token(request)
    await usecase_login_user.do(
        local_repo=local_repo,
        token=token,
        slack_alias=request.session.pop("slack_alias"),
    )
    return templates.TemplateResponse(
        request=request, name="login_complete.html", context={"provider": "fitbit"}
    )


class FitbitNotification(BaseModel):
    collectionType: str | None = None
    date: datetime.date | None = None
    ownerId: str | None = None
    ownerType: str | None = None
    subscriptionId: str | None = None


last_processed_fitbit_notification_per_user: dict[str, datetime.datetime] = {}
last_processed_fitbit_notification_lock = Lock()

DEBOUNCE_NOTIFICATION_DELAY_S = 10


def _is_fitbit_notification_processed(notification: FitbitNotification):
    # Fitbit often calls multiple times for the same event.
    # Ignore this notification if we just processed one recently.
    now = datetime.datetime.now()
    last_fitbit_notification_datetime = last_processed_fitbit_notification_per_user.get(
        notification.ownerId
    )
    already_processed = (
        last_fitbit_notification_datetime
        and (now - last_fitbit_notification_datetime).seconds
        < DEBOUNCE_NOTIFICATION_DELAY_S
    )
    return already_processed


def _mark_fitbit_notification_processed(notification: FitbitNotification):
    now = datetime.datetime.now()
    last_processed_fitbit_notification_per_user[notification.ownerId] = now


@router.post("/fitbit-notification-webhook/")
async def fitbit_notification_webhook(
    notifications: list[FitbitNotification],
    local_fitbit_repo: LocalFitbitRepository = Depends(get_local_fitbit_repository),
):
    logging.info(f"fitbit_notification_webhook: {notifications}")
    for notification in notifications:
        async with last_processed_fitbit_notification_lock:
            if _is_fitbit_notification_processed(notification):
                logging.info(
                    "fitbit_notificaiton_webhook: skipping duplicate notification"
                )
                continue

            try:
                if notification.collectionType == "sleep":
                    new_sleep_data = await usecase_process_new_sleep.do(
                        local_fitbit_repo=local_fitbit_repo,
                        fitbit_userid=notification.ownerId,
                        when=notification.date,
                    )
                    if new_sleep_data:
                        _mark_fitbit_notification_processed(notification)
                elif notification.collectionType == "activities":
                    activity_history = await usecase_process_new_activity.do(
                        local_fitbit_repo=local_fitbit_repo,
                        fitbit_userid=notification.ownerId,
                        when=datetime.datetime.now(),
                    )
                    if activity_history:
                        _mark_fitbit_notification_processed(notification)
            except UserLoggedOutException:
                await usecase_post_user_logged_out.do(
                    fitbit_repo=local_fitbit_repo,
                    fitbit_userid=notification.ownerId,
                )
                break
            except UnknownUserException:
                logging.info("fitbit_notification_webhook: unknown user")
                return Response(status_code=status.HTTP_404_NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

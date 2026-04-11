import datetime as dt
import logging
from enum import StrEnum
from typing import Annotated, Literal

from dependency_injector.wiring import Provide, inject
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict

from slackhealthbot.containers import Container
from slackhealthbot.domain.models.users import HealthUserLookup
from slackhealthbot.domain.usecases.google import (
    usecase_login_user,
    usecase_process_new_data,
)
from slackhealthbot.oauth.config import oauth
from slackhealthbot.routers.dependencies import (
    templates,
)
from slackhealthbot.settings import SecretSettings, Settings

router = APIRouter()

# https://fastapi.tiangolo.com/reference/security/?h=httpauthorizationcredentials#fastapi.security.HTTPBearer--usage
security = HTTPBearer()


# Begin models for the webhook notification request body


class NotificationOperation(StrEnum):
    UPSERT = "UPSERT"
    DELETE = "DELETE"


class NotificationDataType(StrEnum):
    exercise = "exercise"
    distance = "distance"
    sleep = "sleep"
    # More types are possible: https://developers.google.com/health/reference/rest/v4/users.dataTypes.dataPoints#DataPoint
    # But we only support exercise, distance, and sleep.


class NotificationCivilIso8601Interval(BaseModel):
    startTime: dt.datetime
    model_config = ConfigDict(extra="allow")


class NotificationInterval(BaseModel):
    civilIso8601TimeInterval: NotificationCivilIso8601Interval
    model_config = ConfigDict(extra="allow")


class NotificationData(BaseModel):
    healthUserId: str
    # Not using NotificationDataType enum because Google may define additional values
    # not in our enum, which would result in a 422 error in the webhook, instead of the expected 204.
    dataType: str
    operation: NotificationOperation
    intervals: list[NotificationInterval]
    model_config = ConfigDict(extra="allow")


class DataNotification(BaseModel):
    data: NotificationData


class VerificationNotification(BaseModel):
    """
    https://developers.google.com/health/webhooks#endpoint_verification
    Google will verify our webhook route by calling with this payload:
    {"type": "verification"}
    """

    type: Literal["verification"]


# Google can call our webhook route with either exercise/sleep data, or to verify
# that the route is correctly configured.
Notification = DataNotification | VerificationNotification

# End models for the webhook notification request body


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


@router.post("/google-notification-webhook/")
@inject
async def google_notification_webhook(
    notification: Notification,
    background_tasks: BackgroundTasks,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    secret_settings: SecretSettings = Depends(Provide[Container.secret_settings]),
):
    """
    https://developers.google.com/health/webhooks
    """

    # Verify that this webhook comes from a trusted source.
    if credentials.credentials != secret_settings.google_webhook_authorization_token:
        logging.warning(
            "Received google webhook notification without valid credentials"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    logging.info(f"google_notification_webhook: {notification}")

    # Handle a webhook call to verify the webhook configuration.
    # https://developers.google.com/health/webhooks#endpoint_verification
    if isinstance(notification, VerificationNotification):
        return Response(status_code=status.HTTP_200_OK)
    # else: notification is a DataNotification

    data_notification: DataNotification = notification

    # Cases we don't handle:
    if (
        # Unsupported operation:
        data_notification.data.operation
        != NotificationOperation.UPSERT
    ) or (
        # Unsupported data type:
        data_notification.data.dataType
        not in NotificationDataType
    ):
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # Fetch the data for this notification in a background task, so
    # we can return the http response immediately.
    # https://developers.google.com/health/webhooks#respond_to_a_notification
    background_tasks.add_task(
        usecase_process_new_data.do,
        data_type=(
            usecase_process_new_data.DataType.SLEEP
            if data_notification.data.dataType == NotificationDataType.sleep
            # If it's not sleep, it's either distance or exercise google data types.
            # Changes to distance require refreshing exercise data.
            else usecase_process_new_data.DataType.EXERCISE
        ),
        user_lookup=HealthUserLookup(user_id=data_notification.data.healthUserId),
        dates={
            x.civilIso8601TimeInterval.startTime.date()
            for x in data_notification.data.intervals
        },
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)

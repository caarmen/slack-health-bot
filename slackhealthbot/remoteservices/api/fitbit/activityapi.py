import datetime
import json
import logging
from typing import Self

from dependency_injector.wiring import Provide, inject
from pydantic import BaseModel

from slackhealthbot.containers import Container
from slackhealthbot.core.models import OAuthFields
from slackhealthbot.oauth import requests
from slackhealthbot.settings import Settings


class FitbitMinutesInHeartRateZone(BaseModel):
    minutes: int
    type: str


class FitBitActiveZoneMinutes(BaseModel):
    minutesInHeartRateZones: list[FitbitMinutesInHeartRateZone]


class FitbitActivity(BaseModel):
    logId: int
    activeZoneMinutes: FitBitActiveZoneMinutes = FitBitActiveZoneMinutes(
        minutesInHeartRateZones=[]
    )
    activityName: str
    activityTypeId: int
    calories: int
    duration: int
    distance: float | None = None
    distanceUnit: str | None = None


class FitbitActivities(BaseModel):
    activities: list[FitbitActivity]

    @classmethod
    def parse(cls, text: bytes) -> Self:
        return cls(**json.loads(text))


@inject
async def get_activity(
    oauth_token: OAuthFields,
    when: datetime.datetime,
    settings: Settings = Provide[Container.settings],
) -> FitbitActivities | None:
    """
    :raises:
        UserLoggedOutException if the refresh token request fails
    """
    logging.info("get_activity for user")
    when_str = when.strftime("%Y-%m-%dT%H:%M:%S")
    response = await requests.get(
        provider=settings.fitbit_oauth_settings.name,
        token=oauth_token,
        url=f"{settings.fitbit_oauth_settings.base_url}1/user/-/activities/list.json",
        params={
            "beforeDate": when_str,
            "sort": "desc",
            "offset": 0,
            "limit": 1,
        },
    )
    try:
        return FitbitActivities.parse(response.content)
    except Exception as e:
        logging.warning(
            f"Error parsing activity: error {e}, input: {input}", exc_info=e
        )
        return None

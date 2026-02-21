import datetime
import json
import logging
from typing import Self

from pydantic import BaseModel

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
    startTime: str | None = None


class FitbitActivities(BaseModel):
    activities: list[FitbitActivity]

    @classmethod
    def parse(cls, text: bytes) -> Self:
        return cls(**json.loads(text))


async def get_activity(
    oauth_token: OAuthFields,
    when: datetime.datetime,
    settings: Settings,
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


async def get_activities_for_date(
    oauth_token: OAuthFields,
    when: datetime.date,
    settings: Settings,
) -> FitbitActivities | None:
    """
    :raises:
        UserLoggedOutException if the refresh token request fails
    """
    logging.info("get_activities_for_date for user")
    start_date_str = when.strftime("%Y-%m-%d")
    response = await requests.get(
        provider=settings.fitbit_oauth_settings.name,
        token=oauth_token,
        url=f"{settings.fitbit_oauth_settings.base_url}1/user/-/activities/list.json",
        params={
            "afterDate": start_date_str,
            "sort": "asc",
            "offset": 0,
            "limit": 100,
        },
    )
    try:
        activities = FitbitActivities.parse(response.content)
        return _filter_activities_for_date(activities, when)
    except Exception as e:
        logging.warning(
            f"Error parsing activity list: error {e}, input: {input}", exc_info=e
        )
        return None


def _filter_activities_for_date(
    activities: FitbitActivities,
    when: datetime.date,
) -> FitbitActivities:
    filtered: list[FitbitActivity] = []
    for activity in activities.activities:
        if activity.startTime:
            try:
                activity_date = datetime.date.fromisoformat(
                    activity.startTime.split("T")[0]
                )
            except ValueError:
                activity_date = None
            if activity_date is not None:
                if activity_date > when:
                    break
                if activity_date < when:
                    continue
        filtered.append(activity)
    return FitbitActivities(activities=filtered)

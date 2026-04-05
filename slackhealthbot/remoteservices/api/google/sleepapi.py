import datetime as dt
import logging
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, NonNegativeInt

from slackhealthbot.core.models import OAuthFields
from slackhealthbot.oauth import requests
from slackhealthbot.settings import Settings


def parse_seconds_duration(value: str) -> int:
    return int(value[:-1])


DurationS = Annotated[int, BeforeValidator(parse_seconds_duration)]


class Interval(BaseModel):
    startTime: dt.datetime
    startUtcOffset: DurationS
    endTime: dt.datetime
    endUtcOffset: DurationS
    model_config = ConfigDict(extra="allow")


class SleepSummary(BaseModel):
    minutesAwake: NonNegativeInt
    minutesAsleep: NonNegativeInt
    model_config = ConfigDict(extra="allow")


class SleepMetaData(BaseModel):
    nap: bool = False  # This is documented by Google but not returned!
    model_config = ConfigDict(extra="allow")


class Sleep(BaseModel):
    interval: Interval
    summary: SleepSummary
    metadata: SleepMetaData
    model_config = ConfigDict(extra="allow")


class DataPoint(BaseModel):
    sleep: Sleep
    model_config = ConfigDict(extra="allow")


class GoogleSleep(BaseModel):
    dataPoints: list[DataPoint] = Field(default_factory=list)
    model_config = ConfigDict(extra="allow")


async def get_sleep(
    oauth_token: OAuthFields,
    when: dt.date,
    settings: Settings,
) -> GoogleSleep | None:
    # https://developers.google.com/health/reference/rest/v4/users.dataTypes.dataPoints/list
    end_date_str = (when + dt.timedelta(days=1)).strftime("%Y-%m-%d")
    """
    Example:
      "dataPoints": [
    {
      "name": "users/xxx/dataTypes/sleep/dataPoints/yyy",
      "dataSource": {
        "recordingMethod": "MANUAL",
        "platform": "FITBIT"
      },
      "sleep": {
        "interval": {
          "startTime": "2026-04-04T18:39:00Z",
          "startUtcOffset": "7200s",
          "endTime": "2026-04-05T02:39:00Z",
          "endUtcOffset": "7200s"
        },
        "type": "CLASSIC",
        "stages": [
          {
            "startTime": "2026-04-04T18:39:00Z",
            "startUtcOffset": "7200s",
            "endTime": "2026-04-05T02:39:00Z",
            "endUtcOffset": "7200s",
            "type": "ASLEEP",
            "createTime": "2026-04-05T02:39:44.295167Z",
            "updateTime": "2026-04-05T02:39:44.295167Z"
          }
        ],
        "metadata": {
          "stagesStatus": "REJECTED_SERVER",
          "processed": true,
          "externalId": ""
        },
        "summary": {
          "minutesInSleepPeriod": "480",
          "minutesAfterWakeUp": "0",
          "minutesToFallAsleep": "0",
          "minutesAsleep": "480",
          "minutesAwake": "0",
          "stagesSummary": [
            {
              "type": "ASLEEP",
              "minutes": "480",
              "count": "1"
            }   
          ]   
        },  
        "createTime": "2026-04-05T02:39:44.295167Z",
        "updateTime": "2026-04-05T02:39:44.648127Z"
      }   
    },
    """
    # From the api documentation:
    # Data points in the response will be ordered by the interval start time in descending order.
    # Note that the api doesn't expose any ordering parameters.
    response = await requests.get(
        provider=settings.google_oauth_settings.name,
        token=oauth_token,
        url="/v4/users/me/dataTypes/sleep/dataPoints",
        params={
            "filter": f"sleep.interval.civil_end_time < {end_date_str}",
        },
    )
    logging.info(f"Google health sleep response: {response.json()}")

    google_sleep = GoogleSleep.model_validate(response.json())
    # We were only able to request sleeps ending before the end of the given date.
    # We have to filter by hand to exclude any sleeps ended before the beginning
    # of the given date.

    google_sleep.dataPoints = [
        x for x in google_sleep.dataPoints if x.sleep.interval.endTime.date() == when
    ]
    return google_sleep

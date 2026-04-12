import datetime as dt
import logging
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from slackhealthbot.core.models import OAuthFields
from slackhealthbot.oauth import requests
from slackhealthbot.settings import Settings


def parse_seconds_duration(value: str) -> int:
    return int(value[:-1])


DurationS = Annotated[int, BeforeValidator(parse_seconds_duration)]


class TimeInHeartRateZones(BaseModel):
    lightTime: DurationS
    moderateTime: DurationS
    vigorousTime: DurationS
    peakTime: DurationS


class MetricsSummary(BaseModel):
    caloriesKcal: float
    heartRateZoneDurations: TimeInHeartRateZones
    distanceMillimeters: int | None = None
    model_config = ConfigDict(extra="allow")


class Interval(BaseModel):
    startTime: dt.datetime
    endTime: dt.datetime
    model_config = ConfigDict(extra="allow")


class Exercise(BaseModel):
    interval: Interval
    metricsSummary: MetricsSummary
    activeDuration: DurationS
    exerciseType: str
    displayName: str
    model_config = ConfigDict(extra="allow")


class Distance(BaseModel):
    millimeters: int
    interval: Interval
    model_config = ConfigDict(extra="allow")


class DataPoint(BaseModel):
    exercise: Exercise | None = None
    distance: Distance | None = None
    name: str | None = None
    model_config = ConfigDict(extra="allow")


class HealthActivities(BaseModel):
    # https://developers.google.com/health/reference/rest/v4/users.dataTypes.dataPoints#DataPoint
    """
    {
      "dataPoints": [
        {
          "name": "users/xxx/dataTypes/exercise/dataPoints/yyy",
          "dataSource": {
            "recordingMethod": "MANUAL",
            "application": {
              "webClientId": "228TSL"
            },
            "platform": "FITBIT"
          },
          "exercise": {
            "interval": {
              "startTime": "2026-04-04T22:53:00Z",
              "startUtcOffset": "7200s",
              "endTime": "2026-04-04T23:23:00Z",
              "endUtcOffset": "7200s"
            },
            "exerciseType": "OTHER",
            "metricsSummary": {
              "caloriesKcal": 23,
              "activeZoneMinutes": "0",
              "heartRateZoneDurations": {
                "lightTime": "0s",
                "moderateTime": "0s",
                "vigorousTime": "0s",
                "peakTime": "0s"
              }
            },
            "exerciseMetadata": {
              "hasGps": false
            },
            "displayName": "Tapis de course",
            "activeDuration": "1800s",
            "updateTime": "2026-04-04T23:23:24.269034Z",
            "createTime": "2026-04-04T23:23:24.269034Z"
          }
        }
      ],
      "nextPageToken": ""
    }
    """

    dataPoints: list[DataPoint] = Field(default_factory=list)
    model_config = ConfigDict(extra="allow")


async def get_activities_for_date(
    oauth_token: OAuthFields,
    when: dt.date,
    settings: Settings,
) -> HealthActivities | None:
    start_date_str = when.strftime("%Y-%m-%d")
    end_date_str = (when + dt.timedelta(days=1)).strftime("%Y-%m-%d")
    exercise_response = await requests.get(
        provider=settings.google_oauth_settings.name,
        token=oauth_token,
        url="/v4/users/me/dataTypes/exercise/dataPoints",
        params={
            "filter": f"exercise.interval.civil_start_time >= {start_date_str} AND exercise.interval.civil_start_time < {end_date_str}",
        },
    )
    logging.info(f"Google health exercise response: {exercise_response.json()}")
    exercises = HealthActivities.model_validate(exercise_response.json())
    if not exercises.dataPoints:
        return exercises

    min_start_time = min((x.exercise.interval.startTime for x in exercises.dataPoints))
    max_end_time = max((x.exercise.interval.endTime for x in exercises.dataPoints))
    min_start_time_str = min_start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    max_end_time_str = max_end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    distance_response = await requests.get(
        provider=settings.google_oauth_settings.name,
        token=oauth_token,
        url="/v4/users/me/dataTypes/distance/dataPoints",
        params={
            "pageSize": 10000,
            "filter": f'distance.interval.start_time >= "{min_start_time_str}" AND distance.interval.start_time < "{max_end_time_str}"',
        },
    )
    logging.info(f"Google health distance response: {distance_response.json()}")
    distances = HealthActivities.model_validate(distance_response.json())

    # Exercsies and distances are sorted in decreasing order of interval start time, according to Google documentation:
    # https://developers.google.com/health/reference/rest/v4/users.dataTypes.dataPoints/list
    distance_index = 0
    distance_point_count = len(distances.dataPoints)
    for exercise_data_point in exercises.dataPoints:
        exercise = exercise_data_point.exercise
        if exercise.metricsSummary.distanceMillimeters is None:
            # WHY GOOGLE, WHY??? :(
            # Calculate the distance
            for distance_index in range(distance_index, distance_point_count):
                distance = distances.dataPoints[distance_index].distance
                # We're going forward in the lists but backward in time.

                # This distance was after the current exercise, keep going
                # until we get to a distance for the current exercise.
                if distance.interval.startTime > exercise.interval.endTime:
                    continue

                # This distance was before the current exercise, we won't find
                # any more distances for this exercise.
                if distance.interval.endTime < exercise.interval.startTime:
                    break

                if exercise.metricsSummary.distanceMillimeters is None:
                    exercise.metricsSummary.distanceMillimeters = 0
                exercise.metricsSummary.distanceMillimeters += distance.millimeters

    return exercises

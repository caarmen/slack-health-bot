import datetime
import logging

from slackhealthbot.core.models import OAuthFields
from slackhealthbot.domain.models.activity import (
    ActivityData,
    ActivityZone,
    ActivityZoneMinutes,
)
from slackhealthbot.domain.models.sleep import SleepData
from slackhealthbot.domain.remoterepository.remotegooglerepository import (
    HealthIds,
    RemoteGoogleRepository,
)
from slackhealthbot.remoteservices.api.google import activityapi, identityapi, sleepapi
from slackhealthbot.settings import Settings


class WebApiGoogleRepository(RemoteGoogleRepository):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

    def parse_oauth_fields(
        self,
        response_data: dict[str, str],
    ) -> OAuthFields:
        return OAuthFields(
            oauth_userid=response_data["userinfo"]["sub"],
            oauth_access_token=response_data["access_token"],
            oauth_refresh_token=response_data["refresh_token"],
            oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(seconds=int(response_data["expires_in"]))
            - datetime.timedelta(minutes=5),
        )

    async def get_identity(
        self,
        oauth_fields: OAuthFields,
    ) -> HealthIds:
        identity: identityapi.Identity = await identityapi.get_identity(
            oauth_token=oauth_fields,
            settings=self.settings,
        )
        return HealthIds(
            fitbit_user_id=identity.legacyUserId,
            health_user_id=identity.healthUserId,
        )

    async def get_activities_for_date(
        self,
        oauth_fields: OAuthFields,
        when: datetime.date,
    ) -> list[tuple[str, ActivityData]]:
        google_activities: activityapi.HealthActivities = (
            await activityapi.get_activities_for_date(
                oauth_token=oauth_fields,
                when=when,
                settings=self.settings,
            )
        )
        domain_activities = [
            (
                x.exercise.displayName,
                remote_service_activity_to_domain_activity(x),
            )
            for x in google_activities.dataPoints
        ]
        return domain_activities

    async def get_sleep(
        self,
        oauth_fields: OAuthFields,
        when: datetime.date,
    ) -> SleepData | None:
        sleep: sleepapi.GoogleSleep = await sleepapi.get_sleep(
            oauth_token=oauth_fields,
            when=when,
            settings=self.settings,
        )
        return remote_service_sleep_to_domain_sleep(sleep) if sleep else None


def remote_service_activity_type(exercise: activityapi.Exercise) -> int:
    # https://developers.google.com/health/reference/rest/v4/users.dataTypes.dataPoints#Exercise.ExerciseType
    # WHY GOOGLE?
    # Google has only a handful of exercise types, much less than the Fitbit api.
    # "Treadmill" isn't one of them, unfortunately.
    # Just by testing, we see that the displayName was "Tapis de course", for one account, for
    # a treadmill activity.
    # This is not very reliable. We'll have to revisit this when the Google apis become more stable.
    if exercise.exerciseType == "OTHER":
        if exercise.displayName == "Tapis de course":
            return 91064
    if exercise.exerciseType == "WALKING":
        return 90013
    if exercise.exerciseType == "BIKING":
        return 90001

    return 99999


def remote_service_activity_to_domain_activity(
    data_point: activityapi.DataPoint,
) -> ActivityData:
    data_point_id = data_point.name.rsplit("/", 1)[-1]
    return ActivityData(
        log_id=data_point_id,
        type_id=remote_service_activity_type(data_point.exercise),
        logged_at=data_point.exercise.interval.startTime,
        calories=data_point.exercise.metricsSummary.caloriesKcal,
        distance_km=data_point.exercise.metricsSummary.distanceMillimeters
        / (1000 * 1000),
        total_minutes=data_point.exercise.activeDuration / 60,
        zone_minutes=[
            ActivityZoneMinutes(
                zone=ActivityZone.PEAK,
                minutes=data_point.exercise.metricsSummary.heartRateZoneDurations.peakTime
                // 60,
            ),
            ActivityZoneMinutes(
                zone=ActivityZone.CARDIO,
                minutes=data_point.exercise.metricsSummary.heartRateZoneDurations.vigorousTime
                // 60,
            ),
            ActivityZoneMinutes(
                zone=ActivityZone.FAT_BURN,
                minutes=data_point.exercise.metricsSummary.heartRateZoneDurations.moderateTime
                // 60,
            ),
            ActivityZoneMinutes(
                zone=ActivityZone.OUT_OF_ZONE,
                minutes=data_point.exercise.metricsSummary.heartRateZoneDurations.lightTime
                // 60,
            ),
        ],
    )


def remote_service_sleep_to_domain_sleep(
    remote: sleepapi.GoogleSleep | None,
) -> SleepData | None:
    if not remote:
        return None
    main_sleep_item = next(
        (item for item in remote.dataPoints if item.sleep.metadata.nap is False), None
    )
    if not main_sleep_item:
        logging.warning("No main sleep found")
        return None

    interval: sleepapi.Interval = main_sleep_item.sleep.interval
    return SleepData(
        start_time=interval.startTime.replace(tzinfo=None)
        + datetime.timedelta(seconds=interval.startUtcOffset),
        end_time=interval.endTime.replace(tzinfo=None)
        + datetime.timedelta(seconds=interval.endUtcOffset),
        sleep_minutes=main_sleep_item.sleep.summary.minutesAsleep,
        wake_minutes=main_sleep_item.sleep.summary.minutesAwake,
    )

import datetime

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from respx import MockRouter

from slackhealthbot.data.database.models import FitbitUser, User
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
)
from slackhealthbot.domain.models.activity import (
    ActivityData,
    ActivityZone,
    ActivityZoneMinutes,
)
from slackhealthbot.domain.models.sleep import SleepData
from slackhealthbot.settings import Settings
from slackhealthbot.tasks.fitbitpoll import Cache, do_poll
from tests.testsupport.factories.factories import (
    FitbitActivityFactory,
    FitbitUserFactory,
    UserFactory,
)


@pytest.mark.asyncio
async def test_google_poll_sleep(  # noqa: PLR0913
    local_fitbit_repository: LocalFitbitRepository,
    respx_mock: MockRouter,
    fitbit_factories: tuple[UserFactory, FitbitUserFactory, FitbitActivityFactory],
    client: TestClient,
    settings: Settings,
):
    """
    Given a user with previous sleep data logged
    When we poll google to get new sleep data
    Then the last sleep is updated in the database,
    And a message is posted to slack.
    """
    user_factory, fitbit_user_factory, _ = fitbit_factories

    # Given a user with the given previous sleep data
    user: User = user_factory.create(fitbit=None)
    fitbit_user: FitbitUser = fitbit_user_factory.create(
        user_id=user.id,
        last_sleep_start_time=datetime.datetime(2023, 5, 11, 23, 39, 0),
        last_sleep_end_time=datetime.datetime(2023, 5, 12, 8, 28, 0),
        last_sleep_sleep_minutes=449,
        last_sleep_wake_minutes=80,
        health_user_id="googlehealth123",
        oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
    )

    # Mock google endpoint to return no activity data
    respx_mock.get(
        url=f"{settings.google_oauth_settings.base_url}/v4/users/me/dataTypes/exercise/dataPoints",
    ).mock(Response(status_code=200, json={}))

    # Mock google endpoint to return some sleep data
    respx_mock.get(settings.google_oauth_settings.oidc_url).pass_through()
    respx_mock.get(
        url=f"{settings.google_oauth_settings.base_url}/v4/users/me/dataTypes/sleep/dataPoints",
    ).mock(
        Response(
            status_code=200,
            json={
                "dataPoints": [
                    {
                        "sleep": {
                            "interval": {
                                "startTime": "2026-04-04T18:39:00Z",
                                "startUtcOffset": "7200s",
                                "endTime": "2026-04-05T02:39:00Z",
                                "endUtcOffset": "7200s",
                            },
                            "metadata": {},
                            "summary": {
                                "minutesAsleep": "480",
                                "minutesAwake": "0",
                            },
                        },
                    }
                ]
            },
        )
    )

    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(200))

    # When we poll for new sleep data
    # Use the client as a context manager so that the app lifespan hook is called
    # https://fastapi.tiangolo.com/advanced/testing-events/
    with client:
        await do_poll(
            local_fitbit_repo=local_fitbit_repository,
            cache=Cache(),
            when=datetime.date(2026, 4, 5),
        )

    # Then the last sleep data is updated in the database
    actual_last_sleep_data = await local_fitbit_repository.get_sleep_by_user_lookup(
        user_lookup=fitbit_user.lookup,
    )
    assert actual_last_sleep_data == SleepData(
        start_time=datetime.datetime(2026, 4, 4, 20, 39),
        end_time=datetime.datetime(2026, 4, 5, 4, 39),
        sleep_minutes=480,
        wake_minutes=0,
    )

    assert slack_request.call_count == 1


@pytest.mark.asyncio
async def test_google_poll_activity(  # noqa: PLR0913
    local_fitbit_repository: LocalFitbitRepository,
    respx_mock: MockRouter,
    fitbit_factories: tuple[UserFactory, FitbitUserFactory, FitbitActivityFactory],
    client: TestClient,
    settings: Settings,
):
    """
    Given a user
    When we poll google to get new activity data,
    Then the activity data is updated in the database,
    And a message is posted to slack.
    """
    user_factory, fitbit_user_factory, _ = fitbit_factories

    # Given a user with the given previous sleep data
    user: User = user_factory.create(fitbit=None)
    fitbit_user: FitbitUser = fitbit_user_factory.create(
        user_id=user.id,
        health_user_id="googlehealth123",
        oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
    )

    # Mock google endpoint to return no sleep data
    respx_mock.get(settings.google_oauth_settings.oidc_url).pass_through()
    respx_mock.get(
        url=f"{settings.google_oauth_settings.base_url}/v4/users/me/dataTypes/sleep/dataPoints",
    ).mock(Response(status_code=200, json={}))

    # Mock google endpoint to return some activity data
    respx_mock.get(
        url=f"{settings.google_oauth_settings.base_url}/v4/users/me/dataTypes/exercise/dataPoints",
    ).mock(
        Response(
            status_code=200,
            json={
                "dataPoints": [
                    {
                        "name": "users/xxx/dataTypes/exercise/dataPoints/yyy",
                        "exercise": {
                            "interval": {
                                "startTime": "2026-04-04T22:53:00Z",
                                "startUtcOffset": "7200s",
                                "endTime": "2026-04-04T23:23:00Z",
                                "endUtcOffset": "7200s",
                            },
                            "exerciseType": "WALKING",
                            "metricsSummary": {
                                "caloriesKcal": 23,
                                "activeZoneMinutes": "0",
                                "heartRateZoneDurations": {
                                    "lightTime": "0s",
                                    "moderateTime": "63s",
                                    "vigorousTime": "0s",
                                    "peakTime": "0s",
                                },
                            },
                            "displayName": "Tapis de course",
                            "activeDuration": "1800s",
                        },
                    }
                ],
            },
        )
    )
    # Mock google endpoint to return some distance data
    respx_mock.get(
        url=f"{settings.google_oauth_settings.base_url}/v4/users/me/dataTypes/distance/dataPoints",
    ).mock(
        Response(
            status_code=200,
            json={
                "dataPoints": [
                    {
                        "distance": {
                            "interval": {
                                "startTime": "2026-04-04T22:53:00Z",
                                "startUtcOffset": "7200s",
                                "endTime": "2026-04-04T23:03:00Z",
                                "endUtcOffset": "7200s",
                            },
                            "millimeters": 65381,
                        },
                    },
                    {
                        "distance": {
                            "interval": {
                                "startTime": "2026-04-04T23:03:00Z",
                                "startUtcOffset": "7200s",
                                "endTime": "2026-04-04T23:23:00Z",
                                "endUtcOffset": "7200s",
                            },
                            "millimeters": 55334,
                        },
                    },
                ],
            },
        )
    )

    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(200))

    # When we poll for new sleep data
    # Use the client as a context manager so that the app lifespan hook is called
    # https://fastapi.tiangolo.com/advanced/testing-events/
    with client:
        await do_poll(
            local_fitbit_repo=local_fitbit_repository,
            cache=Cache(),
            when=datetime.date(2026, 4, 4),
        )

    # Then the activity data is updated in the database
    actual_activity_data = (
        await local_fitbit_repository.get_latest_activity_by_user_and_type(
            user_lookup=fitbit_user.lookup,
            type_id=90013,
        )
    )
    assert actual_activity_data == ActivityData(
        log_id="yyy",
        type_id=90013,
        logged_at=datetime.datetime(2026, 4, 4, 22, 53),
        total_minutes=30,
        calories=23,
        distance_km=pytest.approx(0.120715),
        zone_minutes=[
            ActivityZoneMinutes(
                zone=ActivityZone.FAT_BURN,
                minutes=1,
            ),
        ],
    )

    assert slack_request.call_count == 1

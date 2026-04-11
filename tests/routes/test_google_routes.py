import datetime as dt
import json
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import status
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
from slackhealthbot.domain.usecases.google import usecase_process_new_data
from slackhealthbot.settings import Settings
from tests.testsupport.factories.factories import FitbitUserFactory, UserFactory

NOTIFICATION_BODY_VERIFICATION = {
    "type": "verification",
}
NOTIFICATION_BODY_SLEEP = {
    "data": {
        "healthUserId": "123",
        "operation": "UPSERT",
        "dataType": "sleep",
        "intervals": [
            {
                "civilIso8601TimeInterval": {
                    "startTime": "2026-04-11T17:29:00",
                },
            }
        ],
    }
}


@pytest.fixture
def authorization_headers(settings: Settings):
    return {
        "authorization": f"Bearer {settings.secret_settings.google_webhook_authorization_token}"
    }


@pytest.fixture
def fitbit_user(
    user_factory: UserFactory,
    fitbit_user_factory: FitbitUserFactory,
):
    user: User = user_factory.create(
        fitbit=None,
        slack_alias="jdoe",
    )
    return fitbit_user_factory.create(
        user_id=user.id,
        health_user_id="123",
        oauth_expiration_date=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1),
    )


@pytest.mark.parametrize(
    ids=["no auth", "wrong auth"],
    argnames="headers",
    argvalues=[{}, {"Authorization": "Bearer invalid"}],
)
@pytest.mark.parametrize(
    ids=["verification", "sleep"],
    argnames="notification_body",
    argvalues=[NOTIFICATION_BODY_VERIFICATION, NOTIFICATION_BODY_SLEEP],
)
def test_google_webhook_verification_unauthorized(
    client: TestClient,
    headers: dict[str, str],
    notification_body: dict[str, Any],
):
    """
    When the webhook is called without correct authorization
    Then the expected error response is returned.
    """
    with client:
        response = client.post(
            "/google-notification-webhook/",
            headers=headers,
            json=notification_body,
        )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_google_webhook_verification_ok(
    client: TestClient,
    authorization_headers: dict[str, str],
):
    """
    When the webhook is called with correct authorization
    Then the response is successful.
    """
    with client:
        response = client.post(
            "/google-notification-webhook/",
            headers=authorization_headers,
            json=NOTIFICATION_BODY_VERIFICATION,
        )

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_sleep_notification(
    client: TestClient,
    respx_mock: MockRouter,
    authorization_headers: dict[str, str],
    fitbit_user: FitbitUser,
    local_fitbit_repository: LocalFitbitRepository,
    settings: Settings,
):
    """
    Given a fitbit user
    When google calls our webhook for new sleep data for that user,
    Then the webhook returns a successful response,
    And the new sleep data is inserted in the database for that user,
    And a message is posted to slack.
    """

    # Given a fitbit user

    # When google calls our webhook for new sleep data for that user,
    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(200))

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
                                "startTime": "2026-04-10T18:39:00Z",
                                "startUtcOffset": "7200s",
                                "endTime": "2026-04-11T02:39:00Z",
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

    with client:
        response = client.post(
            "/google-notification-webhook/",
            headers=authorization_headers,
            json=NOTIFICATION_BODY_SLEEP,
        )

    # Then the webhook returns a successful response,
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # And the new sleep data is inserted in the database for that user.
    actual_last_sleep_data = await local_fitbit_repository.get_sleep_by_user_lookup(
        user_lookup=fitbit_user.lookup,
    )
    assert actual_last_sleep_data == SleepData(
        start_time=dt.datetime(2026, 4, 10, 20, 39),
        end_time=dt.datetime(2026, 4, 11, 4, 39),
        sleep_minutes=480,
        wake_minutes=0,
    )

    # And a message is posted to slack.
    assert slack_request.call_count == 1
    actual_slack_message = json.loads(slack_request.calls[0].request.content)["text"]
    expected_slack_message = "New sleep from <@jdoe>: \n    • Went to bed at 20:39 \n    • Woke up at 4:39 \n    • Total sleep: 8h 0m \n    • Awake: 0m"
    assert actual_slack_message == expected_slack_message


@pytest.mark.parametrize(
    argnames="data_type",
    argvalues=["exercise", "distance"],
)
@pytest.mark.asyncio
async def test_exercise_notification(
    client: TestClient,
    data_type: str,
    respx_mock: MockRouter,
    authorization_headers: dict[str, str],
    fitbit_user: FitbitUser,
    local_fitbit_repository: LocalFitbitRepository,
    settings: Settings,
):
    """
    Given a fitbit user
    When google calls our webhook for new exercise or distance data for that user,
    Then the webhook returns a successful response,
    And the new data is upserted in the database for that user,
    And a message is posted to slack.
    """

    # Given a fitbit user

    # When google calls our webhook for new exercise data for that user,
    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(200))

    # Mock google endpoint to return some exercise data
    respx_mock.get(settings.google_oauth_settings.oidc_url).pass_through()
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
                                "distanceMillimeters": 120715,
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
    respx_mock.get(
        url=f"{settings.google_oauth_settings.base_url}/v4/users/me/dataTypes/distance/dataPoints",
    ).mock(
        Response(
            status_code=200,
            json={},
        )
    )

    with client:
        response = client.post(
            "/google-notification-webhook/",
            headers=authorization_headers,
            json={
                "data": {
                    "healthUserId": "123",
                    "operation": "UPSERT",
                    "dataType": data_type,
                    "intervals": [
                        {
                            "civilIso8601TimeInterval": {
                                "startTime": "2026-04-11T17:29:00",
                            },
                        }
                    ],
                }
            },
        )

    # Then the webhook returns a successful response,
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # And the new exercise data is inserted in the database for that user.
    actual_activity_data = (
        await local_fitbit_repository.get_latest_activity_by_user_and_type(
            user_lookup=fitbit_user.lookup,
            type_id=90013,
        )
    )
    assert actual_activity_data == ActivityData(
        log_id="yyy",
        type_id=90013,
        logged_at=dt.datetime(2026, 4, 4, 22, 53),
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

    # And a message is posted to slack.
    assert slack_request.call_count == 1


@pytest.mark.usefixtures("fitbit_user")
def test_ignore_unsupported_operation(
    client: TestClient,
    authorization_headers: dict[str, Any],
    respx_mock: MockRouter,
    settings: Settings,
):
    """
    Given a fitbit user
    When google calls our webhook for an unsupported operation on exercise data for that user,
    Then the webhook returns a successful response,
    And no call is made to google to fetch exercise data,
    And no message is posted to slack.
    """

    # Given a fitbit user
    # When google calls our webhook for an unsupported operation on exercise data for that user,
    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(200))

    # Mock google routes
    respx_mock.get(settings.google_oauth_settings.oidc_url).pass_through()
    google_exercise_route = respx_mock.get(
        url=f"{settings.google_oauth_settings.base_url}/v4/users/me/dataTypes/exercise/dataPoints",
    ).mock(Response(status_code=200, json={}))

    with client, patch(
        "slackhealthbot.domain.usecases.google.usecase_process_new_data.do",
        wraps=usecase_process_new_data.do,
    ) as spy_task:
        response = client.post(
            "/google-notification-webhook/",
            headers=authorization_headers,
            json={
                "data": {
                    "healthUserId": "123",
                    "operation": "DELETE",
                    "dataType": "exercise",
                    "intervals": [
                        {
                            "civilIso8601TimeInterval": {
                                "startTime": "2026-04-11T17:29:00",
                            },
                        }
                    ],
                }
            },
        )
    # Verify that the processing had no side-effect for the right reason:
    # ie, the task was not called
    # and not some bug where the task was called and just didn't process the data correctly
    spy_task.assert_not_awaited()

    # Then the webhook returns a successful response,
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # And no call is made to google to fetch exercise data,
    assert not google_exercise_route.called

    # And no message is posted to slack.
    assert not slack_request.called


@pytest.mark.usefixtures("fitbit_user")
def test_ignore_unsupported_data_type(
    client: TestClient,
    respx_mock: MockRouter,
    settings: Settings,
    authorization_headers: dict[str, str],
):
    """
    Given a fitbit user
    When google calls our webhook for an UPSERT on an unsupported data type for that user,
    Then the webhook returns a successful response,
    And no call is made to google to fetch data,
    And no message is posted to slack.
    """

    # Given a fitbit user

    # When google calls our webhook for an UPSERT on an unsupported data type for that user,
    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(200))

    # Mock google routes
    respx_mock.get(settings.google_oauth_settings.oidc_url).pass_through()
    google_exercise_route = respx_mock.get(
        url=f"{settings.google_oauth_settings.base_url}/v4/users/me/dataTypes/exercise/dataPoints",
    ).mock(Response(status_code=200, json={}))
    google_sleep_route = respx_mock.get(
        url=f"{settings.google_oauth_settings.base_url}/v4/users/me/dataTypes/sleep/dataPoints",
    ).mock(Response(status_code=200, json={}))

    with client, patch(
        "slackhealthbot.domain.usecases.google.usecase_process_new_data.do",
        wraps=usecase_process_new_data.do,
    ) as spy_task:
        response = client.post(
            "/google-notification-webhook/",
            headers=authorization_headers,
            json={
                "data": {
                    "healthUserId": "123",
                    "operation": "UPSERT",
                    "dataType": "weight",
                    "intervals": [
                        {
                            "civilIso8601TimeInterval": {
                                "startTime": "2026-04-11T17:29:00",
                            },
                        }
                    ],
                }
            },
        )

    # Verify that the processing had no side-effect for the right reason:
    # ie, the task was not called
    # and not some bug where the task was called and just didn't process the data correctly
    spy_task.assert_not_awaited()

    # Then the webhook returns a successful response,
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # And no call is made to google to fetch exercise data,
    assert not google_exercise_route.called
    assert not google_sleep_route.called

    # And no message is posted to slack.
    assert not slack_request.called


def test_unknown_user(
    client: TestClient,
    respx_mock: MockRouter,
    settings: Settings,
    authorization_headers: dict[str, Any],
):
    """
    When google calls our webhook for an unknown user,
    Then the webhook returns a successful response (yes, it does! see https://developers.google.com/health/webhooks),
    And no call is made to google to fetch data,
    And no message is posted to slack.
    """

    # When google calls our webhook for an unknown user,
    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(200))

    # Mock google routes
    respx_mock.get(settings.google_oauth_settings.oidc_url).pass_through()
    google_exercise_route = respx_mock.get(
        url=f"{settings.google_oauth_settings.base_url}/v4/users/me/dataTypes/exercise/dataPoints",
    ).mock(Response(status_code=200, json={}))
    google_sleep_route = respx_mock.get(
        url=f"{settings.google_oauth_settings.base_url}/v4/users/me/dataTypes/sleep/dataPoints",
    ).mock(Response(status_code=200, json={}))

    with client, patch(
        "slackhealthbot.domain.usecases.google.usecase_process_new_data.do",
        wraps=usecase_process_new_data.do,
    ) as spy_task:

        response = client.post(
            "/google-notification-webhook/",
            headers=authorization_headers,
            json={
                "data": {
                    "healthUserId": "baduserid",
                    "operation": "UPSERT",
                    "dataType": "exercise",
                    "intervals": [
                        {
                            "civilIso8601TimeInterval": {
                                "startTime": "2026-04-11T17:29:00",
                            },
                        }
                    ],
                }
            },
        )
    # Verify that the processing had no side-effect for the right reason:
    # ie, the task was called and realized the user was unknown,
    # and not some bug where the task wasn't even called.
    spy_task.assert_awaited_once()

    # Then the webhook returns a successful response,
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # And no call is made to google to fetch exercise data,
    assert not google_exercise_route.called
    assert not google_sleep_route.called

    # And no message is posted to slack.
    assert not slack_request.called

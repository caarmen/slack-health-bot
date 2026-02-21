import datetime
import json
import re
from operator import attrgetter

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from httpx import Response
from respx import MockRouter

from slackhealthbot.data.database.models import FitbitUser, User
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
)
from slackhealthbot.domain.models.activity import ActivityData, ActivityZone
from slackhealthbot.settings import Settings
from tests.testsupport.factories.factories import (
    FitbitActivityFactory,
    FitbitUserFactory,
    UserFactory,
)
from tests.testsupport.testdata.fitbit_scenarios import (
    FitbitActivityScenario,
    FitbitSleepScenario,
    activity_scenarios,
    sleep_scenarios,
)


@pytest.mark.parametrize(
    ids=sleep_scenarios.keys(),
    argnames="scenario",
    argvalues=sleep_scenarios.values(),
)
@pytest.mark.asyncio
async def test_sleep_notification(  # noqa: PLR0913
    local_fitbit_repository: LocalFitbitRepository,
    client: TestClient,
    respx_mock: MockRouter,
    fitbit_factories: tuple[UserFactory, FitbitUserFactory, FitbitActivityFactory],
    scenario: FitbitSleepScenario,
    settings: Settings,
):
    """
    Given a user with a given previous sleep logged
    When we receive the callback from fitbit that a new sleep is available
    Then the last sleep is updated in the database,
    And the message is posted to slack with the correct icons.
    """

    user_factory, fitbit_user_factory, _ = fitbit_factories

    # Given a user with the given previous sleep data
    user: User = user_factory.create(fitbit=None)
    fitbit_user: FitbitUser = fitbit_user_factory.create(
        user_id=user.id,
        **scenario.input_initial_sleep_data,
        oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
    )

    # Mock fitbit endpoint to return some sleep data
    respx_mock.get(
        url=f"{settings.fitbit_oauth_settings.base_url}1.2/user/-/sleep/date/2023-05-12.json",
    ).mock(Response(status_code=200, json=scenario.input_mock_fitbit_response))

    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(200))

    # When we receive the callback from fitbit that a new sleep is available
    with client:
        response = client.post(
            "/fitbit-notification-webhook/",
            content=json.dumps(
                [
                    {
                        "ownerId": user.fitbit.oauth_userid,
                        "date": "2023-05-12",
                        "collectionType": "sleep",
                    }
                ]
            ),
        )

    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Then the last sleep data is updated in the database
    actual_last_sleep_data = await local_fitbit_repository.get_sleep_by_fitbit_userid(
        fitbit_userid=fitbit_user.oauth_userid,
    )
    assert actual_last_sleep_data == scenario.expected_new_last_sleep_data

    # And the message was sent to slack as expected
    if scenario.expected_icons is not None:
        actual_message = json.loads(slack_request.calls[0].request.content)[
            "text"
        ].replace("\n", "")
        assert re.search(scenario.expected_icons, actual_message)
    else:
        assert not slack_request.calls


@pytest.mark.parametrize(
    ids=activity_scenarios.keys(),
    argnames="scenario",
    argvalues=activity_scenarios.values(),
)
@pytest.mark.asyncio
async def test_activity_notification(  # noqa PLR0913
    local_fitbit_repository: LocalFitbitRepository,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    respx_mock: MockRouter,
    fitbit_factories: tuple[UserFactory, FitbitUserFactory, FitbitActivityFactory],
    scenario: FitbitActivityScenario,
    settings: Settings,
):
    """
    Given a user with a given previous activity logged
    When we receive the callback from fitbit that a new activity is available
    Then the latest activity is updated in the database,
    And the message is posted to slack with the correct pattern.
    """

    user_factory, fitbit_user_factory, fitbit_activity_factory = fitbit_factories
    activity_type_id = 55001

    # Given a user with the given previous activity data
    user: User = user_factory.create(fitbit=None)
    fitbit_user: FitbitUser = fitbit_user_factory.create(
        user_id=user.id,
        oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
    )

    if scenario.input_initial_activity_data:
        fitbit_activity_factory.create(
            fitbit_user_id=fitbit_user.id,
            type_id=activity_type_id,
            **scenario.input_initial_activity_data,
        )

    # Mock fitbit endpoint to return some activity data
    respx_mock.get(
        url=f"{settings.fitbit_oauth_settings.base_url}1/user/-/activities/list.json",
    ).mock(Response(status_code=200, json=scenario.input_mock_fitbit_response))

    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(200))

    if scenario.settings_override:
        for key, value in scenario.settings_override.items():
            settings_attribute_tokens = key.split(".")
            settings_attribute_to_patch = settings_attribute_tokens.pop()
            settings_obj_path_to_patch = ".".join(settings_attribute_tokens)
            settings_obj_to_patch = attrgetter(settings_obj_path_to_patch)(settings)
            monkeypatch.setattr(
                settings_obj_to_patch, settings_attribute_to_patch, value
            )

    # When we receive the callback from fitbit that a new activity is available
    with client:
        response = client.post(
            "/fitbit-notification-webhook/",
            content=json.dumps(
                [
                    {
                        "ownerId": user.fitbit.oauth_userid,
                        "date": "2023-05-12",
                        "collectionType": "activities",
                    }
                ]
            ),
        )

    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Then the latest activity data is updated in the database
    repo_activity: ActivityData = (
        await local_fitbit_repository.get_latest_activity_by_user_and_type(
            fitbit_userid=fitbit_user.oauth_userid,
            type_id=activity_type_id,
        )
    )
    if scenario.expected_new_activity_created:
        assert repo_activity.log_id == scenario.expected_new_last_activity_log_id
    elif scenario.input_initial_activity_data:
        assert repo_activity.log_id == scenario.input_initial_activity_data["log_id"]
    else:
        assert not repo_activity

    # And the message was sent to slack as expected
    if scenario.expected_message_pattern:
        actual_message = json.loads(slack_request.calls[0].request.content)[
            "text"
        ].replace("\n", "")
        assert re.search(scenario.expected_message_pattern, actual_message)
        assert "None" not in actual_message
    else:
        assert not slack_request.calls


@pytest.mark.parametrize(
    argnames=["collectionType"],
    argvalues=[
        ["activities"],
        ["sleep"],
    ],
)
def test_notification_unknown_user(
    client: TestClient,
    collectionType: str,
):
    """
    Given some data in the db
    When we receive a fitbit notification for an unknown user
    Then the webhook returns the expected error.
    """
    # When we receive a fitbit notification for an unknown user
    with client:
        response = client.post(
            "/fitbit-notification-webhook/",
            content=json.dumps(
                [
                    {
                        "ownerId": "UNKNOWNUSER",
                        "date": "2023-05-12",
                        "collectionType": collectionType,
                    }
                ]
            ),
        )

    # Then the webhook returns the expected error.
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_activity_notification_upserts_all_activities(
    local_fitbit_repository: LocalFitbitRepository,
    client: TestClient,
    respx_mock: MockRouter,
    fitbit_factories: tuple[UserFactory, FitbitUserFactory, FitbitActivityFactory],
    settings: Settings,
):
    """
    Given a user with no activities for the day
    When we receive a fitbit activity notification for that day
    Then all activities returned by fitbit for that date are upserted
    """
    user_factory, fitbit_user_factory, _ = fitbit_factories

    # Given a user with fitbit credentials
    user: User = user_factory.create(fitbit=None)
    fitbit_user: FitbitUser = fitbit_user_factory.create(
        user_id=user.id,
        oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
    )

    # And fitbit returns multiple activities for the day
    respx_mock.get(
        url=f"{settings.fitbit_oauth_settings.base_url}1/user/-/activities/list.json",
    ).mock(
        Response(
            status_code=200,
            json={
                "activities": [
                    {
                        "activeZoneMinutes": {"minutesInHeartRateZones": []},
                        "activityName": "Spinning",
                        "activityTypeId": 55001,
                        "logId": 1001,
                        "calories": 76,
                        "duration": 665000,
                    },
                    {
                        "activeZoneMinutes": {
                            "minutesInHeartRateZones": [
                                {
                                    "minutes": 8,
                                    "type": "FAT_BURN",
                                },
                                {
                                    "minutes": 4,
                                    "type": "CARDIO",
                                },
                            ]
                        },
                        "activityName": "Spinning",
                        "activityTypeId": 55001,
                        "logId": 1002,
                        "calories": 90,
                        "duration": 720000,
                    },
                ]
            },
        )
    )

    # And slack webhook is available
    respx_mock.post(f"{settings.secret_settings.slack_webhook_url}").mock(
        return_value=Response(200)
    )

    # When we receive a fitbit notification for activities
    with client:
        response = client.post(
            "/fitbit-notification-webhook/",
            content=json.dumps(
                [
                    {
                        "ownerId": fitbit_user.oauth_userid,
                        "date": "2023-05-12",
                        "collectionType": "activities",
                    }
                ]
            ),
        )

    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Then all activities are upserted
    activity_1 = await local_fitbit_repository.get_activity_by_user_and_log_id(
        fitbit_userid=fitbit_user.oauth_userid,
        log_id=1001,
    )
    activity_2 = await local_fitbit_repository.get_activity_by_user_and_log_id(
        fitbit_userid=fitbit_user.oauth_userid,
        log_id=1002,
    )

    assert activity_1 is not None
    assert activity_2 is not None
    zone_minutes = {x.zone: x.minutes for x in activity_2.zone_minutes}
    assert zone_minutes.get(ActivityZone.FAT_BURN) == 8  # noqa: PLR2004
    assert zone_minutes.get(ActivityZone.CARDIO) == 4  # noqa: PLR2004

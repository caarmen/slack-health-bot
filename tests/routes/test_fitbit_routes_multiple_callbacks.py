"""
Tests for the fitbit routes being called multiple times
"""

import datetime
import json
import re

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from httpx import AsyncClient, Response
from respx import MockRouter

from slackhealthbot.data.database.models import FitbitUser, User
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
)
from slackhealthbot.domain.models.activity import ActivityData
from slackhealthbot.domain.models.sleep import SleepData
from slackhealthbot.main import app, lifespan
from slackhealthbot.routers.fitbit import datetime as dt_to_freeze
from slackhealthbot.settings import Settings
from tests.testsupport.actions.parallel_requests import (
    execute_parallel_requests,
    mock_delayed_responses,
)
from tests.testsupport.factories.factories import (
    FitbitActivityFactory,
    FitbitUserFactory,
    UserFactory,
)
from tests.testsupport.mock.builtins import freeze_time
from tests.testsupport.testdata.fitbit_scenarios import (
    FitbitActivityScenario,
    FitbitSleepScenario,
    activity_scenarios,
    sleep_scenarios,
)


@pytest.mark.asyncio
async def test_multiple_sleep_notifications(  # noqa PLR0913
    local_fitbit_repository: LocalFitbitRepository,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    respx_mock: MockRouter,
    fitbit_factories: tuple[UserFactory, FitbitUserFactory, FitbitActivityFactory],
    settings: Settings,
):
    """
    Given a user with a given previous sleep logged
    When we receive multiple callbacks from fitbit that new different sleep logs are available
    Then the latest sleep is updated in the database,
    And the messages are posted to slack with the correct patterns.
    """

    user_factory, fitbit_user_factory, _ = fitbit_factories

    # Given a user with the given previous sleep data
    user: User = user_factory.create(fitbit=None)
    fitbit_user: FitbitUser = fitbit_user_factory.create(
        user_id=user.id,
        oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
        last_sleep_start_time=datetime.datetime(2023, 5, 11, 23, 39, 0),
        last_sleep_end_time=datetime.datetime(2023, 5, 12, 8, 28, 0),
        last_sleep_sleep_minutes=449,
        last_sleep_wake_minutes=80,
    )

    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(200))

    # Mock fitbit endpoint to return some sleep data
    respx_mock.get(
        url=f"{settings.fitbit_oauth_settings.base_url}1.2/user/-/sleep/date/2023-05-13.json",
    ).mock(
        Response(
            status_code=200,
            json={
                "sleep": [
                    {
                        "startTime": "2023-05-13T00:40:00.000",
                        "endTime": "2023-05-13T09:27:30.000",
                        "duration": 31620000,
                        "type": "classic",
                        "isMainSleep": True,
                        "levels": {
                            "summary": {
                                "asleep": {"minutes": 495},
                                "awake": {"minutes": 130},
                            },
                        },
                    },
                ]
            },
        )
    )

    # When we receive the first callback from fitbit that new sleep is available
    freeze_time(
        monkeypatch,
        dt_module_to_freeze=dt_to_freeze,
        frozen_datetime_args=(2023, 5, 12, 9, 0, 0),
    )
    with client:
        response = client.post(
            "/fitbit-notification-webhook/",
            content=json.dumps(
                [
                    {
                        "ownerId": user.fitbit.oauth_userid,
                        "date": "2023-05-13",
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
    assert actual_last_sleep_data == SleepData(
        start_time=datetime.datetime(2023, 5, 13, 0, 40, 0),
        end_time=datetime.datetime(2023, 5, 13, 9, 27, 30),
        sleep_minutes=495,
        wake_minutes=130,
    )

    # And the message was sent to slack as expected
    assert slack_request.call_count == 1
    actual_message = json.loads(slack_request.calls[-1].request.content)[
        "text"
    ].replace("\n", "")
    assert re.search("⬆️.*⬆️.*⬆️.*⬆️", actual_message)

    # When we receive the second callback from fitbit that new sleep is available
    freeze_time(
        monkeypatch,
        dt_module_to_freeze=dt_to_freeze,
        frozen_datetime_args=(2023, 5, 14, 10, 0, 0),
    )
    respx_mock.get(
        url=f"{settings.fitbit_oauth_settings.base_url}1.2/user/-/sleep/date/2023-05-14.json",
    ).mock(
        Response(
            status_code=200,
            json={
                "sleep": [
                    {
                        "startTime": "2023-05-14T00:40:00.000",
                        "endTime": "2023-05-14T09:27:30.000",
                        "duration": 31620000,
                        "type": "classic",
                        "isMainSleep": True,
                        "levels": {
                            "summary": {
                                "asleep": {"minutes": 500},
                                "awake": {"minutes": 135},
                            },
                        },
                    },
                ]
            },
        )
    )
    with client:
        response = client.post(
            "/fitbit-notification-webhook/",
            content=json.dumps(
                [
                    {
                        "ownerId": user.fitbit.oauth_userid,
                        "date": "2023-05-14",
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
    assert actual_last_sleep_data == SleepData(
        start_time=datetime.datetime(2023, 5, 14, 0, 40, 0),
        end_time=datetime.datetime(2023, 5, 14, 9, 27, 30),
        sleep_minutes=500,
        wake_minutes=135,
    )

    # And the message was sent to slack as expected
    assert slack_request.call_count == 2  # noqa PLR2004
    actual_message = json.loads(slack_request.calls[-1].request.content)[
        "text"
    ].replace("\n", "")
    assert re.search("➡️.*➡️.*➡️.*➡️", actual_message)


@pytest.mark.asyncio
async def test_duplicate_sleep_notification(
    local_fitbit_repository: LocalFitbitRepository,
    client: TestClient,
    respx_mock: MockRouter,
    fitbit_factories: tuple[UserFactory, FitbitUserFactory, FitbitActivityFactory],
    settings: Settings,
):
    """
    Given a user
    When we receive the callback twice from fitbit that a new sleep is available
    Then the latest sleep is updated in the database,
    And the message is posted to slack only once with the correct pattern.
    """

    user_factory, fitbit_user_factory, _ = fitbit_factories
    scenario: FitbitSleepScenario = sleep_scenarios["No previous sleep data"]

    # Given a user with the given previous sleep data
    user: User = user_factory.create(fitbit=None)
    fitbit_user: FitbitUser = fitbit_user_factory.create(
        user_id=user.id,
        **scenario.input_initial_sleep_data,
        oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
    )

    # Mock fitbit endpoint to return some sleep data
    sleep_request = respx_mock.get(
        url=f"{settings.fitbit_oauth_settings.base_url}1.2/user/-/sleep/date/2023-05-12.json",
    ).mock(Response(status_code=200, json=scenario.input_mock_fitbit_response))

    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(200))

    # When we receive the callback from fitbit that a new activity is available
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
    assert sleep_request.call_count == 1
    actual_last_sleep_data = await local_fitbit_repository.get_sleep_by_fitbit_userid(
        fitbit_userid=fitbit_user.oauth_userid,
    )
    assert actual_last_sleep_data == scenario.expected_new_last_sleep_data

    # And the message was sent to slack as expected
    assert slack_request.call_count == 1
    actual_message = json.loads(slack_request.calls[0].request.content)["text"].replace(
        "\n", ""
    )
    assert re.search(scenario.expected_icons, actual_message)

    # When we receive the callback a second time from fitbit
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
    # Then we don't post to stack a second time
    assert sleep_request.call_count == 1
    assert slack_request.call_count == 1


@pytest.mark.asyncio
async def test_duplicate_activity_sequential_notification(
    local_fitbit_repository: LocalFitbitRepository,
    client: TestClient,
    respx_mock: MockRouter,
    fitbit_factories: tuple[UserFactory, FitbitUserFactory, FitbitActivityFactory],
    settings: Settings,
):
    """
    Given a user
    When we receive the callback twice sequentially from fitbit that a new activity is available
    Then the latest activity is updated in the database,
    And the message is posted to slack only once with the correct pattern.
    """

    user_factory, fitbit_user_factory, _ = fitbit_factories
    activity_type_id = 55001
    scenario: FitbitActivityScenario = activity_scenarios[
        "No previous activity data, new Spinning activity"
    ]

    # Given a user with the given previous activity data
    user: User = user_factory.create(fitbit=None)
    fitbit_user: FitbitUser = fitbit_user_factory.create(
        user_id=user.id,
        oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
    )

    # Mock fitbit endpoint to return some activity data
    activity_request = respx_mock.get(
        url=f"{settings.fitbit_oauth_settings.base_url}1/user/-/activities/list.json",
    ).mock(Response(status_code=200, json=scenario.input_mock_fitbit_response))

    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(200))

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
    assert activity_request.call_count == 1
    repo_activity: ActivityData = (
        await local_fitbit_repository.get_latest_activity_by_user_and_type(
            fitbit_userid=fitbit_user.oauth_userid,
            type_id=activity_type_id,
        )
    )
    assert repo_activity.log_id == scenario.expected_new_last_activity_log_id

    # And the message was sent to slack as expected
    assert slack_request.call_count == 1
    actual_message = json.loads(slack_request.calls[0].request.content)["text"].replace(
        "\n", ""
    )
    assert re.search(scenario.expected_message_pattern, actual_message)
    assert "None" not in actual_message

    # When we receive the callback a second time from fitbit
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
    # Then we don't post to stack a second time
    assert activity_request.call_count == 1
    assert slack_request.call_count == 1


@pytest.mark.asyncio
async def test_duplicate_activity_parallel_notification(
    local_fitbit_repository: LocalFitbitRepository,
    respx_mock: MockRouter,
    fitbit_factories: tuple[UserFactory, FitbitUserFactory, FitbitActivityFactory],
    settings: Settings,
):
    """
    Given a user
    When we receive the callback multiple times in parallel from fitbit that a new activity is available
    Then the latest activity is updated in the database,
    And the message is posted to slack only once with the correct pattern.
    """

    parallel_requests_count = 10
    user_factory, fitbit_user_factory, _ = fitbit_factories
    activity_type_id = 55001
    scenario: FitbitActivityScenario = activity_scenarios[
        "No previous activity data, new Spinning activity"
    ]

    # Given a user with the given previous activity data
    user: User = user_factory.create(fitbit=None)
    fitbit_user: FitbitUser = fitbit_user_factory.create(
        user_id=user.id,
        oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
    )

    # Mock fitbit endpoint to return some activity data
    activity_request = respx_mock.get(
        url=f"{settings.fitbit_oauth_settings.base_url}1/user/-/activities/list.json",
    )
    mock_delayed_responses(
        route=activity_request,
        mock_responses=[
            Response(status_code=200, json=scenario.input_mock_fitbit_response)
        ]
        * parallel_requests_count,
    )

    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(200))

    # When we receive the callback multiple times in parallel from fitbit that a new activity is available
    async with lifespan(app):

        async def post_webhook(ac: AsyncClient):
            response = await ac.post(
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

        await execute_parallel_requests(
            app=app,
            request_count=parallel_requests_count,
            request_coro=post_webhook,
        )

    # Then the latest activity data is updated in the database
    assert activity_request.call_count == 1
    repo_activity: ActivityData = (
        await local_fitbit_repository.get_latest_activity_by_user_and_type(
            fitbit_userid=fitbit_user.oauth_userid,
            type_id=activity_type_id,
        )
    )
    assert repo_activity.log_id == scenario.expected_new_last_activity_log_id

    # And the message was sent to slack as expected
    assert slack_request.call_count == 1
    actual_message = json.loads(slack_request.calls[0].request.content)["text"].replace(
        "\n", ""
    )
    assert "None" not in actual_message

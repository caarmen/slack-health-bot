"""
Tests for the withings routes being called multiple times
"""

import datetime
import json
import math

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from httpx import AsyncClient, Response
from respx import MockRouter

from slackhealthbot.data.database.models import User
from slackhealthbot.data.database.models import WithingsUser as DbWithingsUser
from slackhealthbot.domain.localrepository.localwithingsrepository import (
    FitnessData,
    LocalWithingsRepository,
)
from slackhealthbot.main import app, lifespan
from slackhealthbot.settings import Settings
from tests.testsupport.actions.parallel_requests import (
    execute_parallel_requests,
    mock_delayed_responses,
)
from tests.testsupport.factories.factories import UserFactory, WithingsUserFactory


@pytest.mark.asyncio
async def test_multiple_notifications(
    local_withings_repository: LocalWithingsRepository,
    client: TestClient,
    respx_mock: MockRouter,
    withings_factories: tuple[UserFactory, WithingsUserFactory],
    settings: Settings,
):
    """
    Given a user with a given previous weight logged
    When we receive multiple callbacks from withings that new different weight logs are available
    Then the latest weight is updated in the database,
    And the messages are posted to slack with the correct patterns.
    """
    # Given a user
    user_factory, withings_user_factory = withings_factories
    user: User = user_factory.create(withings=None)
    db_withings_user: DbWithingsUser = withings_user_factory.create(
        user_id=user.id,
        last_weight=50.2,
        oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
    )

    # Mock withings endpoint to return some weight data
    weight_request = respx_mock.post(
        url=f"{settings.app_settings.withings.base_url}measure",
    ).mock(
        return_value=Response(
            status_code=200,
            json={
                "status": 0,
                "body": {
                    "measuregrps": [
                        {
                            "measures": [
                                {
                                    "value": 50050,
                                    "unit": -3,
                                }
                            ],
                        },
                    ],
                },
            },
        )
    )
    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        url=f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(status_code=200))

    # When we receive the first callback from withings that a new weight is available
    with client:
        client.post(
            "/withings-notification-webhook/",
            data={
                "userid": db_withings_user.oauth_userid,
                "startdate": 1683894606,
                "enddate": 1686570821,
            },
        )
    # Then the last_weight is updated in the database
    assert weight_request.call_count == 1
    fitness_data: FitnessData = (
        await local_withings_repository.get_fitness_data_by_withings_userid(
            withings_userid=db_withings_user.oauth_userid,
        )
    )
    assert math.isclose(fitness_data.last_weight_kg, 50.05)

    # And the message is sent to slack as expected
    assert slack_request.call_count == 1
    actual_message = json.loads(slack_request.calls[-1].request.content)["text"]
    assert "↘️" in actual_message

    # When we receive the second callback from withings that a new weight is available
    weight_request = respx_mock.post(
        url=f"{settings.app_settings.withings.base_url}measure",
    ).mock(
        return_value=Response(
            status_code=200,
            json={
                "status": 0,
                "body": {
                    "measuregrps": [
                        {
                            "measures": [
                                {
                                    "value": 51020,
                                    "unit": -3,
                                }
                            ],
                        },
                    ],
                },
            },
        )
    )
    weight_request.reset()
    with client:
        client.post(
            "/withings-notification-webhook/",
            data={
                "userid": db_withings_user.oauth_userid,
                "startdate": 1683895606,
                "enddate": 1686575821,
            },
        )

    # Then the last_weight is updated in the database
    assert weight_request.call_count == 1
    fitness_data: FitnessData = (
        await local_withings_repository.get_fitness_data_by_withings_userid(
            withings_userid=db_withings_user.oauth_userid,
        )
    )
    assert math.isclose(fitness_data.last_weight_kg, 51.02)

    # And the message is sent to slack as expected
    assert slack_request.call_count == 2  # noqa PLR2004
    actual_message = json.loads(slack_request.calls[-1].request.content)["text"]
    assert "↗️" in actual_message


@pytest.mark.asyncio
async def test_duplicate_weight_sequential_notification(
    local_withings_repository: LocalWithingsRepository,
    client: TestClient,
    respx_mock: MockRouter,
    withings_factories: tuple[UserFactory, WithingsUserFactory],
    settings: Settings,
):
    """
    Given a user with a given previous weight logged
    When we receive the callback twice sequentially from withings that a new weight is available
    Then the last_weight is updated in the database,
    And the message is posted to slack only once
    """

    user_factory, withings_user_factory = withings_factories

    # Given a user
    user: User = user_factory.create(withings=None)
    db_withings_user: DbWithingsUser = withings_user_factory.create(
        user_id=user.id,
        last_weight=50.2,
        oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
    )

    # Mock withings endpoint to return some weight data
    weight_request = respx_mock.post(
        url=f"{settings.app_settings.withings.base_url}measure",
    ).mock(
        return_value=Response(
            status_code=200,
            json={
                "status": 0,
                "body": {
                    "measuregrps": [
                        {
                            "measures": [
                                {
                                    "value": 50050,
                                    "unit": -3,
                                }
                            ],
                        },
                    ],
                },
            },
        )
    )

    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        url=f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(status_code=200))

    # When we receive the callback from withings that a new weight is available
    # Use the client as a context manager so the app can have its lfespan events triggered.
    # https://fastapi.tiangolo.com/advanced/testing-events/
    with client:
        response = client.post(
            "/withings-notification-webhook/",
            data={
                "userid": db_withings_user.oauth_userid,
                "startdate": 1683894606,
                "enddate": 1686570821,
            },
        )

    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Then the last_weight is updated in the database
    assert weight_request.call_count == 1
    fitness_data: FitnessData = (
        await local_withings_repository.get_fitness_data_by_withings_userid(
            withings_userid=db_withings_user.oauth_userid,
        )
    )
    assert math.isclose(fitness_data.last_weight_kg, 50.05)

    # And the message is sent to slack as expected
    assert slack_request.call_count == 1
    actual_message = json.loads(slack_request.calls[0].request.content)["text"]
    assert "↘️" in actual_message

    # When we receive the callback a second time from withings
    with client:
        response = client.post(
            "/withings-notification-webhook/",
            data={
                "userid": db_withings_user.oauth_userid,
                "startdate": 1683894606,
                "enddate": 1686570821,
            },
        )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    # Then we don't post to stack a second time
    assert weight_request.call_count == 1
    assert slack_request.call_count == 1


@pytest.mark.asyncio
async def test_duplicate_weight_parallel_notification(
    local_withings_repository: LocalWithingsRepository,
    respx_mock: MockRouter,
    withings_factories: tuple[UserFactory, WithingsUserFactory],
    settings: Settings,
):
    """
    Given a user with a given previous weight logged
    When we receive the callback multiple times in parallel from withings that a new weight is available
    Then the last_weight is updated in the database,
    And the message is posted to slack only once
    """

    parallel_requests_count = 10
    user_factory, withings_user_factory = withings_factories

    # Given a user
    user: User = user_factory.create(withings=None)
    db_withings_user: DbWithingsUser = withings_user_factory.create(
        user_id=user.id,
        last_weight=50.2,
        oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
    )
    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        url=f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(status_code=200))

    # Mock withings endpoint to return some weight data
    weight_request = respx_mock.post(
        url=f"{settings.app_settings.withings.base_url}measure",
    )
    mock_delayed_responses(
        route=weight_request,
        mock_responses=[
            Response(
                status_code=200,
                json={
                    "status": 0,
                    "body": {
                        "measuregrps": [
                            {
                                "measures": [
                                    {
                                        "value": 50050,
                                        "unit": -3,
                                    }
                                ],
                            },
                        ],
                    },
                },
            )
        ]
        * parallel_requests_count,
    )
    # When we receive the callback multiple times in parallel from withings that a new weight is available
    async with lifespan(app):

        async def post_webhook(ac: AsyncClient):
            response = await ac.post(
                "/withings-notification-webhook/",
                data={
                    "userid": db_withings_user.oauth_userid,
                    "startdate": 1683894606,
                    "enddate": 1686570821,
                },
            )

            assert response.status_code == status.HTTP_204_NO_CONTENT

        await execute_parallel_requests(
            app=app,
            request_count=parallel_requests_count,
            request_coro=post_webhook,
        )

    # Then the last_weight is updated in the database
    assert weight_request.call_count == 1
    fitness_data: FitnessData = (
        await local_withings_repository.get_fitness_data_by_withings_userid(
            withings_userid=db_withings_user.oauth_userid,
        )
    )
    assert math.isclose(fitness_data.last_weight_kg, 50.05)

    # And the message is sent to slack as expected
    assert slack_request.call_count == 1
    actual_message = json.loads(slack_request.calls[0].request.content)["text"]
    assert "↘️" in actual_message

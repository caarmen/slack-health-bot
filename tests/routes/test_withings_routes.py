import dataclasses
import datetime
import json
import math

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from httpx import Response
from respx import MockRouter

from slackhealthbot.data.database.models import User
from slackhealthbot.data.database.models import WithingsUser as DbWithingsUser
from slackhealthbot.domain.localrepository.localwithingsrepository import (
    FitnessData,
    LocalWithingsRepository,
)
from slackhealthbot.settings import settings
from tests.testsupport.factories.factories import UserFactory, WithingsUserFactory


@dataclasses.dataclass
class WeightNotificationScenario:
    input_initial_weight: float | None
    input_new_weight_g: int
    expected_new_latest_weight_kg: float
    expected_icon: str


@pytest.mark.parametrize(
    argnames=["scenario"],
    argvalues=[
        (WeightNotificationScenario(None, 52100, 52.1, ""),),
        (WeightNotificationScenario(52.1, 52200, 52.2, "↗️"),),
        (WeightNotificationScenario(52.1, 53200, 53.2, "⬆️"),),
        (WeightNotificationScenario(53.1, 53000, 53.0, "↘️"),),
        (WeightNotificationScenario(53.0, 51900, 51.9, "⬇️"),),
        (WeightNotificationScenario(52.3, 52300, 52.3, "➡️"),),
    ],
)
@pytest.mark.asyncio
async def test_weight_notification(
    local_withings_repository: LocalWithingsRepository,
    client: TestClient,
    respx_mock: MockRouter,
    withings_factories: tuple[UserFactory, WithingsUserFactory],
    scenario: WeightNotificationScenario,
):
    """
    Given a user with a given previous weight logged
    When we receive the callback from withings that a new weight is available
    Then the last_weight is updated in the database,
    And the message is posted to slack with the correct icon.
    """

    user_factory, withings_user_factory = withings_factories

    # Given a user
    user: User = user_factory.create(withings=None)
    db_withings_user: DbWithingsUser = withings_user_factory.create(
        user_id=user.id,
        last_weight=scenario.input_initial_weight,
        oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
    )
    # The user has the previous weight logged
    assert db_withings_user.last_weight == scenario.input_initial_weight

    # Mock withings endpoint to return some weight data
    respx_mock.post(
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
                                    "value": scenario.input_new_weight_g,
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
    fitness_data: FitnessData = (
        await local_withings_repository.get_fitness_data_by_withings_userid(
            withings_userid=db_withings_user.oauth_userid,
        )
    )
    assert math.isclose(
        fitness_data.last_weight_kg, scenario.expected_new_latest_weight_kg
    )

    # And the message is sent to slack as expected
    actual_message = json.loads(slack_request.calls[0].request.content)["text"]
    assert scenario.expected_icon in actual_message


@pytest.mark.asyncio
async def test_duplicate_weight_notification(
    local_withings_repository: LocalWithingsRepository,
    client: TestClient,
    respx_mock: MockRouter,
    withings_factories: tuple[UserFactory, WithingsUserFactory],
):
    """
    Given a user with a given previous weight logged
    When we receive the callback twice from withings that a new weight is available
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


def test_notification_unknown_user(
    client: TestClient,
):
    """
    Given some data in the db
    When we receive a withings notification for an unknown user
    Then the webhook returns the expected error.
    """
    # When we receive a withings notification for an unknown user
    with client:
        response = client.post(
            "/withings-notification-webhook/",
            data={
                "userid": "UNKNOWNUSER",
                "startdate": 1683894606,
                "enddate": 1686570821,
            },
        )

    # Then the webhook returns the expected error.
    assert response.status_code == status.HTTP_404_NOT_FOUND

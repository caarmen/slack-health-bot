import datetime
import enum
import json
import math
import re

import pytest
from authlib.integrations.starlette_client.apps import StarletteOAuth2App
from fastapi import status
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from httpx import Response
from respx import MockRouter

from slackhealthbot.data.database.models import User as DbUser
from slackhealthbot.data.database.models import WithingsUser as DbWithingsUser
from slackhealthbot.domain.localrepository.localwithingsrepository import (
    FitnessData,
    LocalWithingsRepository,
    User,
    UserIdentity,
)
from slackhealthbot.settings import settings
from tests.testsupport.factories.factories import UserFactory, WithingsUserFactory


@pytest.mark.asyncio
async def test_refresh_token_ok(
    local_withings_repository: LocalWithingsRepository,
    client: TestClient,
    respx_mock: MockRouter,
    withings_factories: tuple[UserFactory, WithingsUserFactory],
):
    """
    Given a user whose access token is expired
    When we receive the callback from withings that a new weight is available
    Then the access token is refreshed
    And the latest weight is updated in the database,
    And the message is posted to slack with the correct pattern.
    """
    user_factory, withings_user_factory = withings_factories

    # Given a user
    user: DbUser = user_factory.create(withings=None)
    db_withings_user: DbWithingsUser = withings_user_factory.create(
        user_id=user.id,
        last_weight=50.2,
        oauth_access_token="some old access token",
        oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(days=1),
    )

    # Mock withings oauth refresh token success
    oauth_token_refresh_request = respx_mock.post(
        url=f"{settings.app_settings.withings.base_url}v2/oauth2",
    ).mock(
        Response(
            status_code=200,
            json={
                "status": 0,
                "body": {
                    "userid": user.withings.oauth_userid,
                    "access_token": "some new access token",
                    "refresh_token": "some new refresh token",
                    "expires_in": 600,
                },
            },
        )
    )

    # Mock withings endpoint to return some weight data
    withings_weight_request = respx_mock.post(
        url=f"{settings.app_settings.withings.base_url}measure",
    ).mock(
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
        ),
    )

    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        url=f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(status_code=200))

    # When we receive the callback from withings that a new weight is available
    with client as client_ctx:
        response = client_ctx.post(
            "/withings-notification-webhook/",
            data={
                "userid": db_withings_user.oauth_userid,
                "startdate": 1683894606,
                "enddate": 1686570821,
            },
        )

    assert response.status_code == status.HTTP_204_NO_CONTENT

    repo_user: User = await local_withings_repository.get_user_by_withings_userid(
        withings_userid=db_withings_user.oauth_userid,
    )
    # Then the access token is refreshed.
    assert withings_weight_request.call_count == 1
    assert (
        withings_weight_request.calls[0].request.headers["authorization"]
        == "Bearer some new access token"
    )
    assert oauth_token_refresh_request.call_count == 1
    assert repo_user.oauth_data.oauth_access_token == "some new access token"
    assert repo_user.oauth_data.oauth_refresh_token == "some new refresh token"

    # And the last_weight is updated in the database
    assert math.isclose(repo_user.fitness_data.last_weight_kg, 50.05)

    # And the message is sent to slack as expected
    actual_message = json.loads(slack_request.calls[0].request.content)["text"]
    assert "↘️" in actual_message


@pytest.mark.asyncio
async def test_refresh_token_fail(
    local_withings_repository: LocalWithingsRepository,
    client: TestClient,
    respx_mock: MockRouter,
    withings_factories: tuple[UserFactory, WithingsUserFactory],
):
    """
    Given a user whose access token is expired and invalid
    When we receive the callback from withings that a new weight is available
    Then the access token refresh fails
    And no weight is updated in the database,
    And the message is posted to slack about the user being logged out
    """
    user_factory, withings_user_factory = withings_factories

    # Given a user
    user: DbUser = user_factory.create(withings=None, slack_alias="jdoe")
    db_withings_user: DbWithingsUser = withings_user_factory.create(
        user_id=user.id,
        last_weight=None,
        oauth_access_token="some old invalid access token",
        oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(days=1),
    )

    # Mock withings oauth refresh token fail
    oauth_token_refresh_request = respx_mock.post(
        url=f"{settings.app_settings.withings.base_url}v2/oauth2",
    ).mock(Response(status_code=200, json={"status": 401}))

    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        url=f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(status_code=200))

    # When we receive the callback from withings that a new weight is available
    with client as client_ctx:
        response = client_ctx.post(
            "/withings-notification-webhook/",
            data={
                "userid": db_withings_user.oauth_userid,
                "startdate": 1683894606,
                "enddate": 1686570821,
            },
        )

    assert response.status_code == status.HTTP_204_NO_CONTENT

    repo_user: User = await local_withings_repository.get_user_by_withings_userid(
        withings_userid=db_withings_user.oauth_userid,
    )
    # Then the access token is not refreshed.
    assert oauth_token_refresh_request.call_count == 1
    assert repo_user.oauth_data.oauth_access_token == "some old invalid access token"

    # And no new weight data is updated in the database
    repo_fitness_data: FitnessData = (
        await local_withings_repository.get_fitness_data_by_withings_userid(
            withings_userid=repo_user.identity.withings_userid,
        )
    )
    assert repo_fitness_data.last_weight_kg is None

    # And a message was sent to slack about the user being logged out
    actual_message = json.loads(slack_request.calls[0].request.content)["text"].replace(
        "\n", ""
    )
    assert re.search(
        "Oh no <@jdoe>, looks like you were logged out of withings! 😳.", actual_message
    )


class LoginScenario(enum.Enum):
    EXISTING_WITHINGS_USER = 0
    EXISTING_NOT_WITHINGS_USER = 1
    NEW_USER = 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    argnames=["scenario"],
    argvalues=[[x] for x in LoginScenario],
)
async def test_login_success(
    local_withings_repository: LocalWithingsRepository,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    withings_factories: tuple[UserFactory, WithingsUserFactory],
    scenario: LoginScenario,
):
    user_factory, withings_user_factory = withings_factories
    # Given a user
    if scenario == LoginScenario.EXISTING_WITHINGS_USER:
        user: DbUser = user_factory.create(withings=None, slack_alias="jdoe")
        withings_user_factory.create(
            user_id=user.id,
            oauth_userid="user123",
        )
    elif scenario == LoginScenario.EXISTING_NOT_WITHINGS_USER:
        user_factory.create(withings=None, slack_alias="jdoe")

    # mock authlib's generation of a URL on withings
    async def mock_authorize_redirect(*_args, **_kwargs):
        return RedirectResponse("https://fakewithings.com", status_code=302)

    monkeypatch.setattr(
        StarletteOAuth2App,
        "authorize_redirect",
        mock_authorize_redirect,
    )
    # Simulate the user starting the withings login
    with client:
        response: Response = client.get(
            "/v1/withings-authorization/jdoe",
            follow_redirects=False,
        )
    assert response.status_code == status.HTTP_302_FOUND
    assert response.headers["location"] == "https://fakewithings.com"

    # mock authlib's token response
    async def mock_authorize_access_token(*_args, **_kwargs):
        return {
            "userid": "user123",
            "access_token": "some access token",
            "refresh_token": "some refresh token",
            "expires_in": 3600,
        }

    monkeypatch.setattr(
        StarletteOAuth2App,
        "authorize_access_token",
        mock_authorize_access_token,
    )

    # Simulate withings's response to the sleep and activity subscriptions
    async def mock_post(*_args, **_kwargs):
        return Response(status_code=200, json={"status": 0})

    monkeypatch.setattr(
        StarletteOAuth2App,
        "post",
        mock_post,
    )

    # Simulate withings calling us back to finish the login
    with client:
        response: Response = client.get(
            "/withings-oauth-webhook",
        )

    assert response.status_code == status.HTTP_200_OK

    # Verify that we have the expected data in the db
    repo_user = await local_withings_repository.get_user_by_withings_userid(
        "user123",
    )
    assert repo_user.identity == UserIdentity(
        withings_userid="user123",
        slack_alias="jdoe",
    )

    assert repo_user.oauth_data.oauth_access_token == "some access token"
    assert repo_user.oauth_data.oauth_refresh_token == "some refresh token"


@pytest.mark.asyncio
async def test_logged_out(
    local_withings_repository: LocalWithingsRepository,
    client: TestClient,
    respx_mock: MockRouter,
    withings_factories: tuple[UserFactory, WithingsUserFactory],
):
    """
    Given a user whose access token is invalid
    When we receive the callback from withings that a new weight is available
    Then no weight is updated in the database
    And a message is posted to slack about the user being logged out
    """

    user_factory, withings_user_factory = withings_factories

    # Given a user
    user: DbUser = user_factory.create(withings=None, slack_alias="jdoe")
    db_withings_user: DbWithingsUser = withings_user_factory.create(
        user_id=user.id,
        last_weight=None,
        oauth_access_token="some invalid access token",
        oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
    )

    # Mock withings endpoint to return an unauthorized error
    withings_weight_request = respx_mock.post(
        url=f"{settings.app_settings.withings.base_url}measure",
    ).mock(return_value=Response(status_code=200, json={"status": 401}))

    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(200))
    # When we receive the callback from withings that a new weight is available
    with client as client_ctx:
        response = client_ctx.post(
            "/withings-notification-webhook/",
            data={
                "userid": db_withings_user.oauth_userid,
                "startdate": 1683894606,
                "enddate": 1686570821,
            },
        )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    repo_user: User = await local_withings_repository.get_user_by_withings_userid(
        withings_userid=db_withings_user.oauth_userid,
    )

    # Then the access token is not refreshed.
    assert withings_weight_request.call_count == 1
    assert repo_user.oauth_data.oauth_access_token == "some invalid access token"

    # And no new weight data is updated in the database
    repo_fitness_data: FitnessData = (
        await local_withings_repository.get_fitness_data_by_withings_userid(
            withings_userid=repo_user.identity.withings_userid,
        )
    )
    assert repo_fitness_data.last_weight_kg is None

    # And a message was sent to slack about the user being logged out
    actual_message = json.loads(slack_request.calls[0].request.content)["text"].replace(
        "\n", ""
    )
    assert re.search(
        "Oh no <@jdoe>, looks like you were logged out of withings! 😳.", actual_message
    )

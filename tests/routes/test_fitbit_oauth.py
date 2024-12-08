import datetime
import enum
import json
import re

import pytest
from authlib.integrations.starlette_client.apps import StarletteOAuth2App
from fastapi import status
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from httpx import Response
from respx import MockRouter

from slackhealthbot.data.database.models import FitbitUser, User
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
    UserIdentity,
)
from slackhealthbot.domain.models.activity import ActivityData
from slackhealthbot.settings import settings
from tests.testsupport.factories.factories import (
    FitbitActivityFactory,
    FitbitUserFactory,
    UserFactory,
)
from tests.testsupport.fixtures.fitbit_scenarios import activity_scenarios


@pytest.mark.asyncio
async def test_refresh_token_ok(
    local_fitbit_repository: LocalFitbitRepository,
    client: TestClient,
    respx_mock: MockRouter,
    fitbit_factories: tuple[UserFactory, FitbitUserFactory, FitbitActivityFactory],
):
    """
    Given a user whose access token is expired
    When we receive the callback from fitbit that a new activity is available
    Then the access token is refreshed
    And the latest activity is updated in the database,
    And the message is posted to slack with the correct pattern.
    """

    user_factory, fitbit_user_factory, _ = fitbit_factories

    scenario = activity_scenarios["No previous activity data, new Spinning activity"]
    activity_type_id = scenario.input_mock_fitbit_response["activities"][0][
        "activityTypeId"
    ]

    # Given a user
    user: User = user_factory.create(fitbit=None)
    fitbit_user: FitbitUser = fitbit_user_factory.create(
        user_id=user.id,
        oauth_access_token="some old access token",
        oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(days=1),
    )

    # Mock fitbit oauth refresh token success
    oauth_token_refresh_request = respx_mock.post(
        url=f"{settings.fitbit_oauth_settings.base_url}oauth2/token",
    ).mock(
        Response(
            status_code=200,
            json={
                "user_id": user.fitbit.oauth_userid,
                "access_token": "some new access token",
                "refresh_token": "some new refresh token",
                "expires_in": 600,
            },
        )
    )

    # Mock fitbit endpoint to return some activity data
    fitbit_activity_request = respx_mock.get(
        url=f"{settings.fitbit_oauth_settings.base_url}1/user/-/activities/list.json",
    ).mock(
        side_effect=[
            Response(status_code=200, json=scenario.input_mock_fitbit_response),
        ]
    )

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

    repo_user = await local_fitbit_repository.get_user_by_fitbit_userid(
        fitbit_userid=fitbit_user.oauth_userid
    )

    # Then the access token is refreshed.
    assert fitbit_activity_request.call_count == 1
    assert (
        fitbit_activity_request.calls[0].request.headers["authorization"]
        == "Bearer some new access token"
    )
    assert oauth_token_refresh_request.call_count == 1
    assert repo_user.oauth_data.oauth_access_token == "some new access token"
    assert repo_user.oauth_data.oauth_refresh_token == "some new refresh token"

    # And the latest activity data is updated in the database
    repo_activity: ActivityData = (
        await local_fitbit_repository.get_latest_activity_by_user_and_type(
            fitbit_userid=repo_user.identity.fitbit_userid,
            type_id=activity_type_id,
        )
    )
    assert repo_activity.log_id == scenario.expected_new_last_activity_log_id

    # And the message was sent to slack as expected
    actual_message = json.loads(slack_request.calls[0].request.content)["text"].replace(
        "\n", ""
    )
    assert re.search(scenario.expected_message_pattern, actual_message)
    assert "None" not in actual_message


@pytest.mark.asyncio
async def test_refresh_token_fail(
    local_fitbit_repository: LocalFitbitRepository,
    client: TestClient,
    respx_mock: MockRouter,
    fitbit_factories: tuple[UserFactory, FitbitUserFactory, FitbitActivityFactory],
):
    """
    Given a user whose access token is expired and invalid
    When we receive the callback from fitbit that a new activity is available
    Then the access token refresh fails
    And no latest activity is updated in the database,
    And the message is posted to slack about the user being logged out
    """

    user_factory, fitbit_user_factory, _ = fitbit_factories

    scenario = activity_scenarios["No previous activity data, new Spinning activity"]
    activity_type_id = scenario.input_mock_fitbit_response["activities"][0][
        "activityTypeId"
    ]

    # Given a user
    user: User = user_factory.create(fitbit=None, slack_alias="jdoe")
    fitbit_user: FitbitUser = fitbit_user_factory.create(
        user_id=user.id,
        oauth_access_token="some old invalid access token",
        oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(days=1),
    )

    # Mock fitbit oauth refresh token failure
    oauth_token_refresh_request = respx_mock.post(
        url=f"{settings.fitbit_oauth_settings.base_url}oauth2/token",
    ).mock(Response(status_code=401))

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

    repo_user = await local_fitbit_repository.get_user_by_fitbit_userid(
        fitbit_userid=fitbit_user.oauth_userid
    )

    # Then the access token is not refreshed.
    assert oauth_token_refresh_request.call_count == 1
    assert repo_user.oauth_data.oauth_access_token == "some old invalid access token"

    # And no new activity data is updated in the database
    repo_activity: ActivityData = (
        await local_fitbit_repository.get_latest_activity_by_user_and_type(
            fitbit_userid=repo_user.identity.fitbit_userid,
            type_id=activity_type_id,
        )
    )
    assert repo_activity is None

    # And a message was sent to slack about the user being logged out
    actual_message = json.loads(slack_request.calls[0].request.content)["text"].replace(
        "\n", ""
    )
    assert re.search(
        "Oh no <@jdoe>, looks like you were logged out of fitbit! 😳.", actual_message
    )


class LoginScenario(enum.Enum):
    EXISTING_FITBIT_USER = 0
    EXISTING_NOT_FITBIT_USER = 1
    NEW_USER = 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    argnames=["scenario"],
    argvalues=[[x] for x in LoginScenario],
)
async def test_login_success(
    local_fitbit_repository: LocalFitbitRepository,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    fitbit_factories: tuple[UserFactory, FitbitUserFactory, FitbitActivityFactory],
    scenario: LoginScenario,
):
    user_factory, fitbit_user_factory, _ = fitbit_factories

    # Given a user
    if scenario == LoginScenario.EXISTING_FITBIT_USER:
        user: User = user_factory.create(fitbit=None, slack_alias="jdoe")
        fitbit_user_factory.create(
            user_id=user.id,
            oauth_userid="user123",
        )
    elif scenario == LoginScenario.EXISTING_NOT_FITBIT_USER:
        user_factory.create(fitbit=None, slack_alias="jdoe")

    # mock authlib's generation of a URL on fitbit
    async def mock_authorize_redirect(*_args, **_kwags):
        return RedirectResponse("https://fakefitbit.com", status_code=302)

    monkeypatch.setattr(
        StarletteOAuth2App,
        "authorize_redirect",
        mock_authorize_redirect,
    )
    # Simulate the user starting the fitbit login
    with client:
        response: Response = client.get(
            "/v1/fitbit-authorization/jdoe",
            follow_redirects=False,
        )
    assert response.status_code == status.HTTP_302_FOUND
    assert response.headers["location"] == "https://fakefitbit.com"

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

    # Simulate fitbit's response to the sleep and activity subscriptions
    async def mock_post(*_args, **_kwargs):
        return Response(status_code=200, json={})

    monkeypatch.setattr(
        StarletteOAuth2App,
        "post",
        mock_post,
    )

    # Simulate fitbit calling us back to finish the login
    with client:
        response: Response = client.get(
            "/fitbit-oauth-webhook",
        )

    assert response.status_code == status.HTTP_200_OK

    # Verify that we have the expected data in the db
    repo_user = await local_fitbit_repository.get_user_by_fitbit_userid(
        "user123",
    )
    assert repo_user.identity == UserIdentity(
        fitbit_userid="user123",
        slack_alias="jdoe",
    )

    assert repo_user.oauth_data.oauth_access_token == "some access token"
    assert repo_user.oauth_data.oauth_refresh_token == "some refresh token"


@pytest.mark.asyncio
async def test_logged_out(
    local_fitbit_repository: LocalFitbitRepository,
    client: TestClient,
    respx_mock: MockRouter,
    fitbit_factories: tuple[UserFactory, FitbitUserFactory, FitbitActivityFactory],
):
    """
    Given a user whose access token is invalid
    When we receive the callback from fitbit that a new activity is available
    Then no activity is updated in the database
    And a message is posted to slack about the user being logged out
    """

    user_factory, fitbit_user_factory, _ = fitbit_factories

    activity_type_id = 55001

    # Given a user
    user: User = user_factory.create(fitbit=None, slack_alias="jdoe")
    fitbit_user: FitbitUser = fitbit_user_factory.create(
        user_id=user.id,
        oauth_access_token="some invalid access token",
        oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
    )

    # Mock fitbit endpoint to return an unauthorized error
    fitbit_activity_request = respx_mock.get(
        url=f"{settings.fitbit_oauth_settings.base_url}1/user/-/activities/list.json",
    ).mock(Response(status_code=401))

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

    repo_user = await local_fitbit_repository.get_user_by_fitbit_userid(
        fitbit_userid=fitbit_user.oauth_userid
    )

    # Then the access token is not refreshed.
    assert fitbit_activity_request.call_count == 1
    assert repo_user.oauth_data.oauth_access_token == "some invalid access token"

    # And no new activity data is updated in the database
    repo_activity: ActivityData = (
        await local_fitbit_repository.get_latest_activity_by_user_and_type(
            fitbit_userid=repo_user.identity.fitbit_userid,
            type_id=activity_type_id,
        )
    )
    assert repo_activity is None

    # And a message was sent to slack about the user being logged out
    actual_message = json.loads(slack_request.calls[0].request.content)["text"].replace(
        "\n", ""
    )
    assert re.search(
        "Oh no <@jdoe>, looks like you were logged out of fitbit! 😳.", actual_message
    )

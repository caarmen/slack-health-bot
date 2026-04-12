import dataclasses
import datetime as dt
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
from slackhealthbot.domain.models.users import HealthUserLookup
from slackhealthbot.remoteservices.api.google.identityapi import Identity
from slackhealthbot.settings import Settings
from tests.testsupport.factories.factories import (
    FitbitActivityFactory,
    FitbitUserFactory,
    UserFactory,
)


@dataclasses.dataclass
class LoginScenario:
    id: str
    existing_slack_user: bool
    existing_fitbit_user_data: dict[str, str] | None
    google_identity_response: Identity
    expected_user_identity: UserIdentity


@pytest.mark.asyncio
@pytest.mark.parametrize(
    argnames="scenario",
    ids=lambda s: s.id,
    argvalues=[
        LoginScenario(
            # the user has a withings account but never logged in with
            # fitbit or google yet.
            id="withings user",
            existing_slack_user=True,
            existing_fitbit_user_data=None,
            google_identity_response=Identity(
                legacyUserId="legacyfitbit123",
                healthUserId="healthuser123",
            ),
            expected_user_identity=UserIdentity(
                fitbit_userid="legacyfitbit123",
                health_user_id="healthuser123",
                slack_alias="jdoe",
            ),
        ),
        LoginScenario(
            id="legacy fitbit user",
            existing_slack_user=True,
            existing_fitbit_user_data={
                "oauth_userid": "legacyfitbit123",
                "fitbit_user_id": "legacyfitbit123",
                "health_user_id": None,
            },
            google_identity_response=Identity(
                legacyUserId="legacyfitbit123",
                healthUserId="healthuser123",
            ),
            expected_user_identity=UserIdentity(
                fitbit_userid="legacyfitbit123",
                health_user_id="healthuser123",
                slack_alias="jdoe",
            ),
        ),
        LoginScenario(
            id="fitbit + google user",
            existing_slack_user=True,
            existing_fitbit_user_data={
                "oauth_userid": "legacyfitbit123",
                "fitbit_user_id": "legacyfitbit123",
                "health_user_id": "healthuser123",
            },
            google_identity_response=Identity(
                legacyUserId="legacyfitbit123",
                healthUserId="healthuser123",
            ),
            expected_user_identity=UserIdentity(
                fitbit_userid="legacyfitbit123",
                health_user_id="healthuser123",
                slack_alias="jdoe",
            ),
        ),
        LoginScenario(
            id="google only user",
            existing_slack_user=True,
            existing_fitbit_user_data={
                "oauth_userid": "googleuserid123",
                "fitbit_user_id": None,
                "health_user_id": "healthuser123",
            },
            google_identity_response=Identity(
                legacyUserId=None,
                healthUserId="healthuser123",
            ),
            expected_user_identity=UserIdentity(
                fitbit_userid=None,
                health_user_id="healthuser123",
                slack_alias="jdoe",
            ),
        ),
        LoginScenario(
            id="new fitbit + google user",
            existing_slack_user=False,
            existing_fitbit_user_data=None,
            google_identity_response=Identity(
                legacyUserId="legacyfitbit123",
                healthUserId="healthuser123",
            ),
            expected_user_identity=UserIdentity(
                fitbit_userid="legacyfitbit123",
                health_user_id="healthuser123",
                slack_alias="jdoe",
            ),
        ),
        LoginScenario(
            id="new google only user",
            existing_slack_user=False,
            existing_fitbit_user_data=None,
            google_identity_response=Identity(
                legacyUserId=None,
                healthUserId="healthuser123",
            ),
            expected_user_identity=UserIdentity(
                fitbit_userid=None,
                health_user_id="healthuser123",
                slack_alias="jdoe",
            ),
        ),
    ],
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
    user: User = user_factory.create(fitbit=None, slack_alias="jdoe")
    if scenario.existing_fitbit_user_data:
        fitbit_user_factory.create(
            user_id=user.id,
            **scenario.existing_fitbit_user_data,
        )

    # mock authlib's generation of a URL on google
    async def mock_authorize_redirect(*_args, **_kwags):
        return RedirectResponse("https://fakegoogle.com", status_code=302)

    monkeypatch.setattr(
        StarletteOAuth2App,
        "authorize_redirect",
        mock_authorize_redirect,
    )
    # Simulate the user starting the google login
    with client:
        response: Response = client.get(
            "/v1/google-authorization/jdoe",
            follow_redirects=False,
        )
    assert response.status_code == status.HTTP_302_FOUND
    assert response.headers["location"] == "https://fakegoogle.com"

    # mock authlib's token response
    async def mock_authorize_access_token(*_args, **_kwargs):
        return {
            "userid": "user123",
            "access_token": "some access token",
            "refresh_token": "some refresh token",
            "expires_in": 3600,
            "userinfo": {
                "sub": "googleuserid123",
            },
        }

    monkeypatch.setattr(
        StarletteOAuth2App,
        "authorize_access_token",
        mock_authorize_access_token,
    )

    # Simulate google's response to the identity request
    async def mock_get_identity(*_args, **_kwargs):
        return Response(
            status_code=200,
            json=scenario.google_identity_response.model_dump(),
        )

    monkeypatch.setattr(
        StarletteOAuth2App,
        "get",
        mock_get_identity,
    )
    # Simulate google calling us back to finish the login
    with client:
        response: Response = client.get(
            "/google-oauth-webhook",
        )

    assert response.status_code == status.HTTP_200_OK

    # Verify that we have the expected data in the db
    repo_user = await local_fitbit_repository.get_user_by_lookup(
        HealthUserLookup(user_id=scenario.expected_user_identity.health_user_id)
    )
    assert repo_user.identity == scenario.expected_user_identity

    assert repo_user.oauth_data.oauth_access_token == "some access token"
    assert repo_user.oauth_data.oauth_refresh_token == "some refresh token"


@pytest.mark.asyncio
async def test_logged_out(
    client: TestClient,
    respx_mock: MockRouter,
    user_factory: UserFactory,
    fitbit_user_factory: FitbitUserFactory,
    local_fitbit_repository: LocalFitbitRepository,
    settings: Settings,
):
    """
    Given a user whose access token is invalid
    When we receive the callback from google that a new sleep is available,
    Then the webhook response is successful,
    And no sleep is updated in the database
    And a message is posted to slack about the user being logged out
    """

    # Given a user
    user: User = user_factory.create(fitbit=None, slack_alias="jdoe")
    fitbit_user: FitbitUser = fitbit_user_factory.create(
        user_id=user.id,
        health_user_id="123",
        oauth_access_token="some invalid access token",
        oauth_expiration_date=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1),
    )

    # Mock google endpoint to return an unauthorized error
    respx_mock.get(settings.google_oauth_settings.oidc_url).pass_through()
    google_sleep_route = respx_mock.get(
        url=f"{settings.google_oauth_settings.base_url}/v4/users/me/dataTypes/sleep/dataPoints",
    ).mock(return_value=Response(status_code=status.HTTP_401_UNAUTHORIZED, json={}))

    # Mock an empty ok response from the slack webhook
    slack_route = respx_mock.post(f"{settings.secret_settings.slack_webhook_url}").mock(
        return_value=Response(200)
    )

    # When we receive the callback from google that a new sleep is available
    with client:
        response = client.post(
            "/google-notification-webhook/",
            headers={
                "Authorization": f"Bearer {settings.secret_settings.google_webhook_authorization_token}",
            },
            json={
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
            },
        )

    # Then the webhook response is successful,
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Then the access token is not refreshed.
    assert google_sleep_route.call_count == 1
    assert fitbit_user.oauth_access_token == "some invalid access token"

    # And no new sleep data is updated in the database
    actual_last_sleep_data = await local_fitbit_repository.get_sleep_by_user_lookup(
        user_lookup=fitbit_user.lookup,
    )
    assert actual_last_sleep_data is None

    # And a message was sent to slack about the user being logged out
    actual_message = json.loads(slack_route.calls[0].request.content)["text"].replace(
        "\n", ""
    )
    assert re.search(
        "Oh no <@jdoe>, looks like you were logged out of google! 😳.", actual_message
    )

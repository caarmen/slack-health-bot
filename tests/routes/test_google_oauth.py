import dataclasses

import pytest
from authlib.integrations.starlette_client.apps import StarletteOAuth2App
from fastapi import status
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from httpx import Response

from slackhealthbot.data.database.models import User
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
    UserIdentity,
)
from slackhealthbot.domain.models.users import HealthUserLookup
from slackhealthbot.remoteservices.api.google.identityapi import Identity
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

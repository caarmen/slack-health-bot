import datetime
import json
import re

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from respx import MockRouter

from slackhealthbot.data.database.models import FitbitUser, User
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
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
async def test_refresh_token_ok(  # noqa: PLR0913
    client: TestClient,
    respx_mock: MockRouter,
    fitbit_factories: tuple[UserFactory, FitbitUserFactory, FitbitActivityFactory],
    local_fitbit_repository: LocalFitbitRepository,
    settings: Settings,
):
    """
    Given a user whose access token is expired
    When we poll google for sleep data
    Then the access token is refreshed
    And the latest sleep data is updated in the database,
    And the message is posted to slack.
    """

    user_factory, fitbit_user_factory, _ = fitbit_factories

    # Given a user
    user: User = user_factory.create(fitbit=None)
    fitbit_user: FitbitUser = fitbit_user_factory.create(
        user_id=user.id,
        oauth_userid="googleuser123",
        health_user_id="healthuserid123",
        oauth_access_token="some old access token",
        oauth_refresh_token="some old refresh token",
        oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(days=1),
    )

    # Mock google oauth refresh token success
    oauth_token_refresh_request = respx_mock.post(
        url="https://oauth2.googleapis.com/token",
    ).mock(
        Response(
            status_code=200,
            json={
                "user_id": user.fitbit.oauth_userid,
                "access_token": "some new access token",
                "refresh_token": "some old refresh token",
                "expires_in": 600,
            },
        )
    )

    # Mock google endpoint to return no activity data
    respx_mock.get(
        url=f"{settings.google_oauth_settings.base_url}/v4/users/me/dataTypes/exercise/dataPoints",
    ).mock(Response(status_code=200, json={}))

    respx_mock.get(settings.google_oauth_settings.oidc_url).pass_through()
    respx_mock.get("https://www.googleapis.com/oauth2/v3/certs").pass_through()

    # Mock google endpoint to return some sleep data
    google_sleep_request = respx_mock.get(
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
            cache=Cache(),
            when=datetime.date(2026, 4, 5),
        )

        repo_user = await local_fitbit_repository.get_user_by_lookup(fitbit_user.lookup)

        # Then the access token is refreshed.
        assert google_sleep_request.call_count == 1
        assert (
            google_sleep_request.calls[0].request.headers["authorization"]
            == "Bearer some new access token"
        )
        assert oauth_token_refresh_request.call_count == 1
        assert repo_user.oauth_data.oauth_access_token == "some new access token"
        assert repo_user.oauth_data.oauth_refresh_token == "some old refresh token"

        # And the latest sleep data is updated in the database
        actual_last_sleep_data = await local_fitbit_repository.get_sleep_by_user_lookup(
            user_lookup=fitbit_user.lookup,
        )
        assert actual_last_sleep_data == SleepData(
            start_time=datetime.datetime(2026, 4, 4, 20, 39),
            end_time=datetime.datetime(2026, 4, 5, 4, 39),
            sleep_minutes=480,
            wake_minutes=0,
        )

    # And a message was sent to slack
    assert slack_request.call_count == 1


@pytest.mark.asyncio
async def test_logged_out(  # noqa: PLR0913
    local_fitbit_repository: LocalFitbitRepository,
    client: TestClient,
    respx_mock: MockRouter,
    fitbit_factories: tuple[UserFactory, FitbitUserFactory, FitbitActivityFactory],
    settings: Settings,
):
    """
    Given a user whose access token is invalid
    When we poll google for new data
    Then no sleep is updated in the database
    And a message is posted to slack about the user being logged out
    """

    user_factory, fitbit_user_factory, _ = fitbit_factories

    # Given a user
    user: User = user_factory.create(fitbit=None, slack_alias="jdoe")
    fitbit_user: FitbitUser = fitbit_user_factory.create(
        user_id=user.id,
        health_user_id="healthuser123",
        oauth_access_token="some invalid access token",
        last_sleep_sleep_minutes=None,
        oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
    )

    respx_mock.get(settings.google_oauth_settings.oidc_url).pass_through()
    # Mock google endpoints to return an unauthorized error
    unauthorized_payload = {
        "error": {
            "code": 401,
            "message": "Request had invalid authentication credentials. Expected OAuth 2 access token, login ...m/identity/sign-in/web/devconsole-project.",
            "status": "UNAUTHENTICATED",
        }
    }
    respx_mock.get(
        url=f"{settings.google_oauth_settings.base_url}/v4/users/me/dataTypes/sleep/dataPoints",
    ).mock(Response(status_code=401, json=unauthorized_payload))
    google_activity_request = respx_mock.get(
        url=f"{settings.google_oauth_settings.base_url}/v4/users/me/dataTypes/exercise/dataPoints",
    ).mock(Response(status_code=401, json=unauthorized_payload))

    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(200))

    # When we poll for new data
    # Use the client as a context manager so that the app lifespan hook is called
    # https://fastapi.tiangolo.com/advanced/testing-events/
    with client:
        await do_poll(
            local_fitbit_repo=local_fitbit_repository,
            cache=Cache(),
            when=datetime.date(2023, 1, 23),
        )

    repo_user = await local_fitbit_repository.get_user_by_lookup(fitbit_user.lookup)

    # Then the access token is not refreshed.
    assert google_activity_request.call_count == 1
    assert repo_user.oauth_data.oauth_access_token == "some invalid access token"

    # And no new sleep data is updated in the database
    sleep_data = await local_fitbit_repository.get_sleep_by_user_lookup(
        fitbit_user.lookup
    )
    assert sleep_data is None

    # And a message was sent to slack about the user being logged out
    assert slack_request.call_count == 1
    actual_message = json.loads(slack_request.calls[0].request.content)["text"].replace(
        "\n", ""
    )
    assert re.search(
        "Oh no <@jdoe>, looks like you were logged out of google! 😳.", actual_message
    )

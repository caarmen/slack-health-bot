import datetime
import enum
import json
import re

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from respx import MockRouter
from sqlalchemy.ext.asyncio import AsyncSession

from slackhealthbot.data.database.models import FitbitUser, User
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
)
from slackhealthbot.domain.models.activity import ActivityData
from slackhealthbot.domain.remoterepository.remotefitbitrepository import (
    RemoteFitbitRepository,
)
from slackhealthbot.remoteservices.repositories.webhookslackrepository import (
    WebhookSlackRepository,
)
from slackhealthbot.routers.dependencies import fitbit_repository_factory
from slackhealthbot.settings import settings
from slackhealthbot.tasks.fitbitpoll import Cache, do_poll
from tests.testsupport.factories.factories import (
    FitbitActivityFactory,
    FitbitUserFactory,
    UserFactory,
)
from tests.testsupport.fixtures.fitbit_scenarios import activity_scenarios


@pytest.mark.asyncio
async def test_refresh_token_ok(
    mocked_async_session: AsyncSession,
    remote_fitbit_repository: RemoteFitbitRepository,
    client: TestClient,
    respx_mock: MockRouter,
    fitbit_factories: tuple[UserFactory, FitbitUserFactory, FitbitActivityFactory],
):
    """
    Given a user whose access token is expired
    When we poll fitbit for a new activity
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

    # Mock fitbit endpoint to return no sleep data
    respx_mock.get(
        url=f"{settings.fitbit_oauth_settings.base_url}1.2/user/-/sleep/date/2023-01-23.json",
    ).mock(Response(status_code=200, json={"sleep": []}))

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

    # When we poll for new activity data
    # Use the client as a context manager so that the app lifespan hook is called
    # https://fastapi.tiangolo.com/advanced/testing-events/
    with client:
        async with fitbit_repository_factory(mocked_async_session)() as repo:
            await do_poll(
                local_fitbit_repo=repo,
                remote_fitbit_repo=remote_fitbit_repository,
                slack_repo=WebhookSlackRepository(),
                cache=Cache(),
                when=datetime.date(2023, 1, 23),
            )

            repo_user = await repo.get_user_by_fitbit_userid(
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
                await repo.get_latest_activity_by_user_and_type(
                    fitbit_userid=repo_user.identity.fitbit_userid,
                    type_id=activity_type_id,
                )
            )
            assert repo_activity.log_id == scenario.expected_new_last_activity_log_id

            # And the message was sent to slack as expected
            actual_message = json.loads(slack_request.calls[0].request.content)[
                "text"
            ].replace("\n", "")
            assert re.search(scenario.expected_message_pattern, actual_message)
            assert "None" not in actual_message


@pytest.mark.asyncio
async def test_refresh_token_fail(
    local_fitbit_repository: LocalFitbitRepository,
    remote_fitbit_repository: RemoteFitbitRepository,
    client: TestClient,
    respx_mock: MockRouter,
    fitbit_factories: tuple[UserFactory, FitbitUserFactory, FitbitActivityFactory],
):
    """
    Given a user whose access token is expired and invalid
    When we poll fitbit for new activity
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

    # When we poll for new activity data
    # Use the client as a context manager so that the app lifespan hook is called
    # https://fastapi.tiangolo.com/advanced/testing-events/
    with client:
        await do_poll(
            local_fitbit_repo=local_fitbit_repository,
            remote_fitbit_repo=remote_fitbit_repository,
            slack_repo=WebhookSlackRepository(),
            cache=Cache(),
            when=datetime.date(2023, 1, 23),
        )

    repo_user = await local_fitbit_repository.get_user_by_fitbit_userid(
        fitbit_userid=fitbit_user.oauth_userid
    )

    # Then the access token is not refreshed.
    # (Ignore ruff warning about 2 being a magic number)
    assert oauth_token_refresh_request.call_count == 2  # noqa PLR2004
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
    assert slack_request.call_count == 1
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
async def test_logged_out(
    local_fitbit_repository: LocalFitbitRepository,
    remote_fitbit_repository: RemoteFitbitRepository,
    client: TestClient,
    respx_mock: MockRouter,
    fitbit_factories: tuple[UserFactory, FitbitUserFactory, FitbitActivityFactory],
):
    """
    Given a user whose access token is invalid
    When we poll fitbit for new activity
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

    # Mock fitbit endpoints to return an unauthorized error
    respx_mock.get(
        url=f"{settings.fitbit_oauth_settings.base_url}1.2/user/-/sleep/date/2023-01-23.json",
    ).mock(Response(status_code=401))
    fitbit_activity_request = respx_mock.get(
        url=f"{settings.fitbit_oauth_settings.base_url}1/user/-/activities/list.json",
    ).mock(Response(status_code=401))

    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(200))

    # When we poll for new activity data
    # Use the client as a context manager so that the app lifespan hook is called
    # https://fastapi.tiangolo.com/advanced/testing-events/
    with client:
        await do_poll(
            local_fitbit_repo=local_fitbit_repository,
            remote_fitbit_repo=remote_fitbit_repository,
            slack_repo=WebhookSlackRepository(),
            cache=Cache(),
            when=datetime.date(2023, 1, 23),
        )

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
    assert slack_request.call_count == 1
    actual_message = json.loads(slack_request.calls[0].request.content)["text"].replace(
        "\n", ""
    )
    assert re.search(
        "Oh no <@jdoe>, looks like you were logged out of fitbit! 😳.", actual_message
    )

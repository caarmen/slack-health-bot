import asyncio
import datetime
import json
import re
from operator import attrgetter

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from respx import MockRouter

from slackhealthbot.data.database.models import FitbitUser, User
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
)
from slackhealthbot.domain.models.activity import ActivityData
from slackhealthbot.domain.remoterepository.remotefitbitrepository import (
    RemoteFitbitRepository,
)
from slackhealthbot.domain.usecases.fitbit.usecase_update_user_oauth import (
    UpdateTokenUseCase,
)
from slackhealthbot.oauth import fitbitconfig
from slackhealthbot.remoteservices.repositories.webhookslackrepository import (
    WebhookSlackRepository,
)
from slackhealthbot.routers.dependencies import (
    fitbit_repository_factory,
    request_context_fitbit_repository,
)
from slackhealthbot.settings import settings
from slackhealthbot.tasks import fitbitpoll
from slackhealthbot.tasks.fitbitpoll import Cache, do_poll
from tests.testsupport.factories.factories import (
    FitbitActivityFactory,
    FitbitUserFactory,
    UserFactory,
)
from tests.testsupport.fixtures.fitbit_scenarios import (
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
async def test_fitbit_poll_sleep(
    fitbit_repositories: tuple[LocalFitbitRepository, RemoteFitbitRepository],
    respx_mock: MockRouter,
    fitbit_factories: tuple[UserFactory, FitbitUserFactory, FitbitActivityFactory],
    scenario: FitbitSleepScenario,
    client: TestClient,
):
    """
    Given a user with given previous sleep data logged
    When we poll fitbit to get new sleep data
    Then the last sleep is updated in the database,
    And the message is posted to slack with the correct icon.
    """
    local_fitbit_repository, remote_fitbit_repository = fitbit_repositories
    user_factory, fitbit_user_factory, _ = fitbit_factories

    # Given a user with the given previous sleep data
    user: User = user_factory.create(fitbit=None)
    fitbit_user: FitbitUser = fitbit_user_factory.create(
        user_id=user.id,
        **scenario.input_initial_sleep_data,
        oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
    )

    # Mock fitbit endpoint to return no activity data
    respx_mock.get(
        url=f"{settings.fitbit_oauth_settings.base_url}1/user/-/activities/list.json",
    ).mock(Response(status_code=200, json={"activities": []}))

    # Mock fitbit endpoint to return some sleep data
    respx_mock.get(
        url=f"{settings.fitbit_oauth_settings.base_url}1.2/user/-/sleep/date/2023-01-23.json",
    ).mock(Response(status_code=200, json=scenario.input_mock_fitbit_response))

    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(200))

    # When we poll for new sleep data
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
async def test_fitbit_poll_activity(  # noqa PLR0913
    fitbit_repositories: tuple[LocalFitbitRepository, RemoteFitbitRepository],
    respx_mock: MockRouter,
    monkeypatch: pytest.MonkeyPatch,
    fitbit_factories: tuple[UserFactory, FitbitUserFactory, FitbitActivityFactory],
    scenario: FitbitActivityScenario,
    client: TestClient,
):
    """
    Given a user with given previous activity data logged
    When we poll fitbit to get new activity data
    Then the latest activity is updated in the database,
    And the message is posted to slack with the correct pattern.
    """

    local_fitbit_repository, remote_fitbit_repository = fitbit_repositories
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

    # Mock fitbit endpoint to return no sleep data
    respx_mock.get(
        url=f"{settings.fitbit_oauth_settings.base_url}1.2/user/-/sleep/date/2023-01-23.json",
    ).mock(Response(status_code=200, json={"sleep": []}))

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

    # When we poll for new sleep data
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
    else:
        assert not slack_request.calls


@pytest.mark.asyncio
async def test_schedule_fitbit_poll(
    mocked_async_session,
    fitbit_repositories: tuple[LocalFitbitRepository, RemoteFitbitRepository],
    respx_mock: MockRouter,
    fitbit_factories: tuple[UserFactory, FitbitUserFactory, FitbitActivityFactory],
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings.app_settings.fitbit.poll, "enabled", False)
    monkeypatch.setattr(settings.app_settings.fitbit.poll, "interval_seconds", 3)
    sleep_scenario: FitbitSleepScenario = sleep_scenarios["No previous sleep data"]
    activity_scenario: FitbitActivityScenario = activity_scenarios[
        "No previous activity data, new Spinning activity"
    ]

    local_fitbit_repository, remote_fitbit_repository = fitbit_repositories
    user_factory, fitbit_user_factory, _ = fitbit_factories

    user: User = user_factory.create(fitbit=None)
    fitbit_user: FitbitUser = fitbit_user_factory.create(
        user_id=user.id,
        oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
    )

    # Mock fitbit endpoint to return some sleep and activity data
    respx_mock.get(
        url=re.compile(
            f"{settings.fitbit_oauth_settings.base_url}1.2/user/-/sleep/date/[0-9-]*.json"
        ),
    ).mock(Response(status_code=200, json=sleep_scenario.input_mock_fitbit_response))
    respx_mock.get(
        url=f"{settings.fitbit_oauth_settings.base_url}1/user/-/activities/list.json",
    ).mock(Response(status_code=200, json=activity_scenario.input_mock_fitbit_response))

    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(200))

    fitbitconfig.configure(
        UpdateTokenUseCase(
            request_context_fitbit_repository,
            remote_repo=remote_fitbit_repository,
        )
    )
    task = await fitbitpoll.schedule_fitbit_poll(
        initial_delay_s=0,
        local_fitbit_repo_factory=fitbit_repository_factory(mocked_async_session),
        remote_fitbit_repo=remote_fitbit_repository,
        slack_repo=WebhookSlackRepository(),
    )
    await asyncio.sleep(1)
    # Then the last sleep data is updated in the database
    actual_last_sleep_data = await local_fitbit_repository.get_sleep_by_fitbit_userid(
        fitbit_userid=fitbit_user.oauth_userid,
    )
    assert actual_last_sleep_data == sleep_scenario.expected_new_last_sleep_data

    # Then the latest activity data is updated in the database
    repo_activity: ActivityData = (
        await local_fitbit_repository.get_latest_activity_by_user_and_type(
            fitbit_userid=fitbit_user.oauth_userid,
            type_id=55001,
        )
    )
    assert repo_activity.log_id == activity_scenario.expected_new_last_activity_log_id

    # And the messages were sent to slack as expected
    assert slack_request.call_count == 2  # noqa: PLR2004
    actual_sleep_message = json.loads(slack_request.calls[0].request.content)[
        "text"
    ].replace("\n", "")
    assert re.search(sleep_scenario.expected_icons, actual_sleep_message)
    actual_activity_message = json.loads(slack_request.calls[1].request.content)[
        "text"
    ].replace("\n", "")
    assert re.search(
        activity_scenario.expected_message_pattern, actual_activity_message
    )
    task.cancel()

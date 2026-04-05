import datetime

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
async def test_google_poll_sleep(  # noqa: PLR0913
    local_fitbit_repository: LocalFitbitRepository,
    respx_mock: MockRouter,
    fitbit_factories: tuple[UserFactory, FitbitUserFactory, FitbitActivityFactory],
    client: TestClient,
    settings: Settings,
):
    """
    Given a user with previous sleep data logged
    When we poll google to get new sleep data
    Then the last sleep is updated in the database,
    And a message is posted to slack.
    """
    user_factory, fitbit_user_factory, _ = fitbit_factories

    # Given a user with the given previous sleep data
    user: User = user_factory.create(fitbit=None)
    fitbit_user: FitbitUser = fitbit_user_factory.create(
        user_id=user.id,
        last_sleep_start_time=datetime.datetime(2023, 5, 11, 23, 39, 0),
        last_sleep_end_time=datetime.datetime(2023, 5, 12, 8, 28, 0),
        last_sleep_sleep_minutes=449,
        last_sleep_wake_minutes=80,
        health_user_id="googlehealth123",
        oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
    )

    # Mock google endpoint to return no activity data
    respx_mock.get(
        url=f"{settings.google_oauth_settings.base_url}/v4/users/me/dataTypes/exercise/dataPoints",
    ).mock(Response(status_code=200, json={}))

    # Mock google endpoint to return some sleep data
    respx_mock.get(settings.google_oauth_settings.oidc_url).pass_through()
    respx_mock.get(
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
            local_fitbit_repo=local_fitbit_repository,
            cache=Cache(),
            when=datetime.date(2026, 4, 5),
        )

    # Then the last sleep data is updated in the database
    actual_last_sleep_data = await local_fitbit_repository.get_sleep_by_user_lookup(
        user_lookup=fitbit_user.lookup,
    )
    assert actual_last_sleep_data == SleepData(
        start_time=datetime.datetime(2026, 4, 4, 20, 39),
        end_time=datetime.datetime(2026, 4, 5, 4, 39),
        sleep_minutes=480,
        wake_minutes=0,
    )

    assert slack_request.call_count == 1

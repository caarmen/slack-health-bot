import asyncio
import datetime as dt
import json

import pytest
from httpx import Response
from respx import MockRouter

from slackhealthbot.data.database import models
from slackhealthbot.settings import Settings
from slackhealthbot.tasks.post_daily_activities_task import dt as dt_to_freeze
from slackhealthbot.tasks.post_daily_activities_task import post_daily_activities
from tests.testsupport.factories.factories import (
    FitbitActivityFactory,
    FitbitUserFactory,
    UserFactory,
)
from tests.testsupport.mock.builtins import freeze_time


@pytest.mark.asyncio
async def test_post_daily_activities(
    monkeypatch: pytest.MonkeyPatch,
    mocked_async_session,
    respx_mock: MockRouter,
    fitbit_factories: tuple[UserFactory, FitbitUserFactory, FitbitActivityFactory],
    settings: Settings,
):
    """
    Given some daily activity stats for a user and an activity type
      for an all-time record,
      a recent top record,
      a record two days ago,
      and a record today,
    When the scheduled task is called to process daily activities for this activity type,
    Then a message is posted to slack with the expected text.
    """
    user_factory, _, fitbit_activity_factory = fitbit_factories
    old_date = dt.datetime(2023, 3, 4, 15, 44, 33)
    recent_date = dt.datetime(2024, 7, 2, 23, 44, 55)
    today = dt.datetime(2024, 8, 2, 10, 44, 55)
    two_days_ago = today - dt.timedelta(days=2)
    user: models.User = user_factory.create(slack_alias="jdoe")
    activity_type = 90019

    # All-time top stats in the old date:
    fitbit_activity_factory.create(
        fitbit_user_id=user.fitbit.id,
        type_id=activity_type,
        calories=1500,
        distance_km=20.000,
        cardio_minutes=45,
        total_minutes=120,
        fat_burn_minutes=60,
        peak_minutes=None,
        out_of_zone_minutes=None,
        updated_at=old_date,
    )

    # Top stats in the recent date.
    fitbit_activity_factory.create(
        fitbit_user_id=user.fitbit.id,
        type_id=activity_type,
        calories=1000,
        distance_km=18.000,
        cardio_minutes=40,
        total_minutes=115,
        fat_burn_minutes=45,
        peak_minutes=None,
        out_of_zone_minutes=None,
        updated_at=recent_date,
    )

    # Two days ago's stats
    fitbit_activity_factory.create(
        fitbit_user_id=user.fitbit.id,
        type_id=activity_type,
        calories=800,
        distance_km=10.000,
        cardio_minutes=30,
        total_minutes=110,
        fat_burn_minutes=40,
        peak_minutes=None,
        out_of_zone_minutes=None,
        updated_at=two_days_ago,
    )

    # Today's stats
    fitbit_activity_factory.create(
        fitbit_user_id=user.fitbit.id,
        type_id=activity_type,
        calories=805,
        distance_km=9.500,
        cardio_minutes=35,
        total_minutes=116,
        fat_burn_minutes=41,
        peak_minutes=1,
        out_of_zone_minutes=None,
        updated_at=today,
    )

    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(200))

    # Freeze time to just before the scheduled post time.
    freeze_time(
        monkeypatch,
        dt_module_to_freeze=dt_to_freeze,
        frozen_datetime_args=(2024, 8, 2, 23, 49, 59),
    )
    task: asyncio.Task = await post_daily_activities(
        activity_type_ids=set(
            settings.app_settings.fitbit.activities.daily_activity_type_ids
        ),
        post_time=settings.app_settings.fitbit.activities.daily_report_time,
    )

    # Wait for one iteration of the scheduled task:
    # A few seconds = 1 iteration, because now is just before the post time.
    # We expect a timeout because this task runs forever
    # (after posting to slack, it sleeps until the next time it should post).
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(5):
            await task.get_coro()

    assert slack_request.call_count == 1
    actual_activity_message = json.loads(slack_request.calls.last.request.content)[
        "text"
    ]
    expected_activity_message = """New daily Treadmill activity from <@jdoe>:
    • Activity count: 1
    • Total duration: 116 minutes ↗️ New record (last 180 days)! 🏆
    • Total calories: 805 ➡️ 
    • Distance: 9.500 km ➡️  1 day streak! 👏
    • Total fat burn minutes: 41 ➡️ 
    • Total cardio minutes: 35 ↗️ 
    • Total peak minutes: 1  New all-time record! 🏆"""

    assert actual_activity_message == expected_activity_message

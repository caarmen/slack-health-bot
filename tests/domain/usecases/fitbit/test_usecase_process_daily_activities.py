import datetime as dt
import json

import pytest
from httpx import Response
from respx import MockRouter

from slackhealthbot.data.database import models
from slackhealthbot.data.repositories.sqlalchemyfitbitrepository import (
    datetime as dt_to_freeze,
)
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
)
from slackhealthbot.domain.usecases.fitbit import usecase_process_daily_activities
from slackhealthbot.remoteservices.repositories.webhookslackrepository import (
    WebhookSlackRepository,
)
from slackhealthbot.settings import settings
from tests.testsupport.factories.factories import (
    FitbitActivityFactory,
    FitbitUserFactory,
    UserFactory,
)
from tests.testsupport.fixtures.builtins import freeze_time


@pytest.mark.asyncio
async def test_process_daily_activities(
    monkeypatch: pytest.MonkeyPatch,
    local_fitbit_repository: LocalFitbitRepository,
    respx_mock: MockRouter,
    fitbit_factories: tuple[UserFactory, FitbitUserFactory, FitbitActivityFactory],
):
    user_factory, _, fitbit_activity_factory = fitbit_factories
    old_date = dt.datetime(2023, 3, 4, 15, 44, 33)
    recent_date = dt.datetime(2024, 4, 2, 23, 44, 55)
    today = dt.datetime(2024, 8, 2, 10, 44, 55)
    activity_type = 111
    user: models.User = user_factory.create(slack_alias="jdoe")

    # All-time top stats in the old date:
    # - 300 calories
    # - 20 km
    # - 30 minutes total
    # - 25 minutes cardio
    fitbit_activity_factory.create(
        fitbit_user_id=user.fitbit.id,
        type_id=activity_type,
        calories=100,
        distance_km=11.3,
        cardio_minutes=13,
        total_minutes=17,
        fat_burn_minutes=None,
        peak_minutes=None,
        out_of_zone_minutes=None,
        updated_at=old_date,
    )
    fitbit_activity_factory.create(
        fitbit_user_id=user.fitbit.id,
        type_id=activity_type,
        calories=200,
        distance_km=8.7,
        total_minutes=13,
        cardio_minutes=12,
        fat_burn_minutes=None,
        peak_minutes=None,
        out_of_zone_minutes=None,
        updated_at=old_date,
    )

    # Top stats in the recent date.
    # - 200 calories
    # - 10km
    # - 11 minutes total
    # - 9 minutes cardio
    fitbit_activity_factory.create(
        fitbit_user_id=user.fitbit.id,
        type_id=activity_type,
        calories=110,
        distance_km=1.3,
        total_minutes=9,
        cardio_minutes=8,
        fat_burn_minutes=None,
        peak_minutes=None,
        out_of_zone_minutes=None,
        updated_at=recent_date,
    )
    fitbit_activity_factory.create(
        fitbit_user_id=user.fitbit.id,
        type_id=activity_type,
        calories=90,
        distance_km=8.7,
        total_minutes=2,
        cardio_minutes=1,
        fat_burn_minutes=None,
        peak_minutes=None,
        out_of_zone_minutes=None,
        updated_at=recent_date,
    )

    # Stats for today
    # - 250 calories
    # - 15km
    # - 15 minutes total
    # - 12 minutes cardio
    fitbit_activity_factory.create(
        fitbit_user_id=user.fitbit.id,
        type_id=activity_type,
        calories=130,
        distance_km=10.1,
        total_minutes=3,
        cardio_minutes=2,
        fat_burn_minutes=None,
        peak_minutes=None,
        out_of_zone_minutes=None,
        updated_at=today,
    )
    fitbit_activity_factory.create(
        fitbit_user_id=user.fitbit.id,
        type_id=activity_type,
        calories=120,
        distance_km=4.9,
        total_minutes=12,
        cardio_minutes=10,
        fat_burn_minutes=None,
        peak_minutes=None,
        out_of_zone_minutes=None,
        updated_at=today,
    )

    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(200))

    with monkeypatch.context() as mp:
        freeze_time(
            mp,
            dt_module_to_freeze=dt_to_freeze,
            frozen_datetime_args=(2024, 8, 2, 10, 44, 55),
        )
        await usecase_process_daily_activities.do(
            local_fitbit_repo=local_fitbit_repository,
            type_ids={activity_type},
            slack_repo=WebhookSlackRepository(),
        )

    assert slack_request.call_count == 1
    actual_activity_message = json.loads(slack_request.calls.last.request.content)[
        "text"
    ]

    expected_activity_message = """New daily Unknown activity from <@jdoe>:
    • Activity count: 2
    • Total duration: 15 minutes ↗️ New record (last 180 days)! 🏆
    • Total calories: 250 ↗️ New record (last 180 days)! 🏆
    • Distance: 15.000 km ⬆️ New record (last 180 days)! 🏆
    • Total cardio minutes: 12 ↗️ New record (last 180 days)! 🏆"""

    assert actual_activity_message == expected_activity_message

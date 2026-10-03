import datetime as dt
import json
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest
from httpx import Response
from pytest import MonkeyPatch
from respx import MockRouter
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from slackhealthbot.data.database import models
from slackhealthbot.data.repositories.sqlalchemyfitbitrepository import (
    datetime as dt_to_freeze,
)
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
)
from slackhealthbot.domain.models.activity import ActivityData
from slackhealthbot.domain.models.users import HealthUserLookup
from slackhealthbot.domain.usecases.fitbit import usecase_process_daily_activity
from slackhealthbot.main import app
from slackhealthbot.settings import AppSettings, SecretSettings, Settings
from tests.testsupport.factories.factories import UserFactory
from tests.testsupport.mock.builtins import freeze_time

DEFAULT_ACTIVITY_ATTRIBUTES = {
    "total_minutes": 10,
    "calories": 0,
    "zone_minutes": [],
}

ACTIVITY_TYPE_PRIMARY = 90019
ACTIVITY_TYPE_SECONDARY = 90013


@pytest.mark.asyncio
async def test_use_distance_account_single_activity_type(
    *,
    user_factory: UserFactory,
    local_fitbit_repository: LocalFitbitRepository,
    settings: Settings,
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    respx_mock: MockRouter,
):
    """
    Given a configuration with min 20km per day,
    And with a primary activity only,
    And day 1 which exceeded the limit by 1km (21km)
    And day 2 which is under the limit by 0.5km (19.5km)
    And day 3 which exceeded the limit by 0.1km (20.1km)
    When the usecase_process_daily_activity use case is called,
    Then messages are posted to slack,
    And the message for day 2 indicates the actual distance of 19.5km,
    And the message for day 3 indicates a streak of 3 days.
    """
    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(200))

    day1 = dt.datetime(2026, 8, 26, 11, 23, 4)
    day2 = day1 + dt.timedelta(days=1)
    day3 = day2 + dt.timedelta(days=1)

    user: models.User = user_factory.create(slack_alias="jdoe")
    activity_type = 90019

    # Given a configuration with min 20km per day
    custom_conf = f"""
fitbit:
  activities:
    activity_types:
      - name: Treadmill
        id: {activity_type}
        report:
          daily: true
          realtime: false
          fields:
            - distance
          daily_goals:
            distance_km: 20.0
          streak:
            mode: lax
"""
    with _context(
        custom_conf_yaml=custom_conf,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    ):
        # Given day 1 which exceeded the limit by 1km
        await _log_activities(
            monkeypatch,
            local_fitbit_repository,
            day1,
            user,
            primary_dist_km=21,
        )

        # And day 2 which is under the limit by 0.5km
        await _log_activities(
            monkeypatch,
            local_fitbit_repository,
            day2,
            user,
            primary_dist_km=19.5,
        )

        # And day 3 which exceeded the limit by 0.1km (20.1km)
        await _log_activities(
            monkeypatch,
            local_fitbit_repository,
            day3,
            user,
            primary_dist_km=20.1,
        )

    # When the usecase_process_daily_activity use case is called,
    # Then messages are posted to slack,
    # And the message for day 2 indicates the actual distance of 19.5km,
    # And the message for day 3 indicates a streak of 3 days.
    expected_activity_messages = [
        """New daily Treadmill activity from <@jdoe>:
    • Distance: 21.000 km  New all-time record! 🏆 Goal reached! 👍 1 day streak! 👏""",
        """New daily Treadmill activity from <@jdoe>:
    • Distance: 19.500 km ➡️  2 day streak! 👏""",
        """New daily Treadmill activity from <@jdoe>:
    • Distance: 20.100 km ➡️  Goal reached! 👍 3 day streak! 👏""",
    ]

    actual_activity_messages = [
        json.loads(x.request.content)["text"] for x in slack_request.calls
    ]

    assert actual_activity_messages == expected_activity_messages


@dataclass
class DoubleActivityTypeStreakScenario:
    id: str
    day1_primary_km: float
    day1_secondary_km: float | None
    day2_primary_km: float
    day2_secondary_km: float
    expected_slack_messages: list[str]
    expected_day2_credit_km: float | None
    expected_day2_debit_km: float | None


@pytest.mark.parametrize(
    argnames="scenario",
    ids=lambda s: s.id,
    argvalues=[
        # In all scenarios, day 3 logs 20.1 km for the primary activity.
        # The purpose is to see if day 2 breaks or maintains the streak.
        # If day 2 is less than the minimum, but can benefit from some adjustments
        # (from the secondary activity or the km account), then the streak
        # won't be broken.
        DoubleActivityTypeStreakScenario(
            id="Enough primary activity each day, no secondary activity",
            day1_primary_km=21.0,
            day1_secondary_km=None,
            day2_primary_km=22.0,
            day2_secondary_km=None,
            expected_slack_messages=[
                "21.000 km  New all-time record! 🏆 Goal reached! 👍 1 day streak! 👏",
                "22.000 km ➡️ New all-time record! 🏆 Goal reached! 👍 2 day streak! 👏",
                "20.100 km ➡️  Goal reached! 👍 3 day streak! 👏",
            ],
            expected_day2_credit_km=2.0,
            expected_day2_debit_km=None,
        ),
        DoubleActivityTypeStreakScenario(
            id="Enough primary activity each day, some secondary activity",
            day1_primary_km=21.0,
            day1_secondary_km=0.5,
            day2_primary_km=22.0,
            day2_secondary_km=2.3,
            expected_slack_messages=[
                "21.000 km  New all-time record! 🏆 Goal reached! 👍 1 day streak! 👏",
                "22.000 km ➡️ New all-time record! 🏆 Goal reached! 👍 2 day streak! 👏",
                "20.100 km ➡️  Goal reached! 👍 3 day streak! 👏",
            ],
            expected_day2_credit_km=2.0,
            expected_day2_debit_km=None,
        ),
        DoubleActivityTypeStreakScenario(
            id="Not enough primary activity second day, secondary activity compensates second day",
            day1_primary_km=20.05,
            day1_secondary_km=0.5,
            day2_primary_km=18.0,
            day2_secondary_km=2.3,
            expected_slack_messages=[
                "20.050 km  New all-time record! 🏆 Goal reached! 👍 1 day streak! 👏",
                "18.000 km ➡️  2 day streak! 👏",
                "20.100 km ➡️ New all-time record! 🏆 Goal reached! 👍 3 day streak! 👏",
            ],
            expected_day2_credit_km=None,
            expected_day2_debit_km=None,
        ),
        # TDD: this fails currently
        DoubleActivityTypeStreakScenario(
            id="Primary activity only: No enough activity second day, use credit from first day",
            day1_primary_km=23.0,  # 3km credit
            day1_secondary_km=None,
            day2_primary_km=18.0,  # 2km debit
            day2_secondary_km=None,
            expected_slack_messages=[
                "23.000 km  New all-time record! 🏆 Goal reached! 👍 1 day streak! 👏",
                "18.000 km ⬇️  2 day streak! 👏",
                "20.100 km ➡️  Goal reached! 👍 3 day streak! 👏",
            ],
            expected_day2_credit_km=None,
            expected_day2_debit_km=2.0,
        ),
        # TDD: this fails currently
        DoubleActivityTypeStreakScenario(
            id="Primary & secondary activity: Not enough activity second day, use credit from first day",
            day1_primary_km=23.0,  # 3km credit
            day1_secondary_km=5.2,
            # 1km debit would be enough, but we first add 0.1 from the secondary activity.
            # Now we only need 0.9km debit
            day2_primary_km=19.0,
            day2_secondary_km=0.1,
            expected_slack_messages=[
                "23.000 km  New all-time record! 🏆 Goal reached! 👍 1 day streak! 👏",
                "19.000 km ↘️  2 day streak! 👏",
                "20.100 km ➡️  Goal reached! 👍 3 day streak! 👏",
            ],
            expected_day2_credit_km=None,
            expected_day2_debit_km=0.9,
        ),
        DoubleActivityTypeStreakScenario(
            id="Primary activity only: Not enough activity second day, not enough credit, lost streak",
            day1_primary_km=23.0,  # 3km credit
            day1_secondary_km=None,
            day2_primary_km=5.0,  # 3km credit not enough, so no debit
            day2_secondary_km=None,
            expected_slack_messages=[
                "23.000 km  New all-time record! 🏆 Goal reached! 👍 1 day streak! 👏",
                "5.000 km ⬇️",
                "20.100 km ⬆️  Goal reached! 👍 1 day streak! 👏",
            ],
            expected_day2_credit_km=None,
            expected_day2_debit_km=None,
        ),
        DoubleActivityTypeStreakScenario(
            # Secondary activities don't have credit
            id="Primary & secondary activity: Not enough activity second day, not enough credit, lost streak",
            day1_primary_km=23.0,  # 3km credit
            day1_secondary_km=5.2,
            day2_primary_km=16.0,  # 3km credit not enough, so no debit
            day2_secondary_km=0.1,
            expected_slack_messages=[
                "23.000 km  New all-time record! 🏆 Goal reached! 👍 1 day streak! 👏",
                "16.000 km ⬇️",
                "20.100 km ↗️  Goal reached! 👍 1 day streak! 👏",
            ],
            expected_day2_credit_km=None,
            expected_day2_debit_km=None,
        ),
        # TDD: this fails currently
        DoubleActivityTypeStreakScenario(
            id="Combine credit and secondary activity",
            day1_primary_km=23.0,  # 3km credit
            day1_secondary_km=5.2,
            # 3km debit wouldn't be enough, but we manage:
            # Get 1.2 from the secondary activity, now we only need 2.8 debit.
            day2_primary_km=16.0,  # 2.8 km debit
            day2_secondary_km=1.2,
            expected_slack_messages=[
                "23.000 km  New all-time record! 🏆 Goal reached! 👍 1 day streak! 👏",
                "16.000 km ⬇️  2 day streak! 👏",
                "20.100 km ↗️  Goal reached! 👍 3 day streak! 👏",
            ],
            expected_day2_credit_km=None,
            expected_day2_debit_km=2.8,
        ),
    ],
)
@pytest.mark.asyncio
async def test_use_distance_account_with_secondary_activity_type(
    *,
    user_factory: UserFactory,
    local_fitbit_repository: LocalFitbitRepository,
    mocked_async_session: AsyncSession,
    settings: Settings,
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    respx_mock: MockRouter,
    scenario: DoubleActivityTypeStreakScenario,
):
    """
    Given a configuration with min 20km per day,
    And with primary and secondary activities,
    And day 1 with the given distances,
    And day 2 with the given distances,
    And day 3 with a primary activity meeting the minimum,
    When the usecase_process_daily_activity use cases is called,
    Then the expected credit_km is set for day 2,
    And the expected debit_km is set for day 2,
    And the expected messages are posted to slack.
    """
    # Mock an empty ok response from the slack webhook
    slack_request = respx_mock.post(
        f"{settings.secret_settings.slack_webhook_url}"
    ).mock(return_value=Response(200))

    day1 = dt.datetime(2026, 8, 26, 11, 23, 4)
    day2 = day1 + dt.timedelta(days=1)
    day3 = day2 + dt.timedelta(days=1)

    user: models.User = user_factory.create(slack_alias="jdoe")

    # Given a configuration with min 20km per day
    # And with primary and secondary activities
    custom_conf = f"""
fitbit:
  activities:
    activity_types:
      - name: Treadmill
        id: {ACTIVITY_TYPE_PRIMARY}
        report:
          daily: true
          realtime: false
          fields:
            - distance
          daily_goals:
            distance_km: 20.0
          streak:
            mode: lax
            secondary_activity_type_id: {ACTIVITY_TYPE_SECONDARY}
"""
    with _context(
        custom_conf_yaml=custom_conf,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    ):
        # And day 1 with the given distances,
        await _log_activities(
            monkeypatch,
            local_fitbit_repository,
            day1,
            user,
            primary_dist_km=scenario.day1_primary_km,
            secondary_dist_km=scenario.day1_secondary_km,
        )

        # And day 2 with the given distances,
        await _log_activities(
            monkeypatch,
            local_fitbit_repository,
            day2,
            user,
            primary_dist_km=scenario.day2_primary_km,
            secondary_dist_km=scenario.day2_secondary_km,
        )

        # And day 3 with a primary activity meeting the minimum,
        await _log_activities(
            monkeypatch,
            local_fitbit_repository,
            day3,
            user,
            primary_dist_km=20.1,
        )
    # When the usecase_process_daily_activity use cases is called,

    actual_day2_distance_account = (
        await mocked_async_session.scalars(
            statement=select(
                models.DistanceAccount,
            ).where(
                and_(
                    models.DistanceAccount.fitbit_user_id == user.fitbit.id,
                    models.DistanceAccount.type_id == ACTIVITY_TYPE_PRIMARY,
                    models.DistanceAccount.date == day2.date(),
                )
            )
        )
    ).one_or_none()
    # Then the expected credit_km is set for day 2,
    actual_day2_credit_km, actual_day2_debit_km = (
        (actual_day2_distance_account.credit_km, actual_day2_distance_account.debit_km)
        if actual_day2_distance_account
        else (None, None)
    )
    assert actual_day2_credit_km == pytest.approx(scenario.expected_day2_credit_km)
    # And the expected debit_km is set for day 2,
    assert actual_day2_debit_km == pytest.approx(scenario.expected_day2_debit_km)
    # And the expected messages are posted to slack.
    actual_activity_messages = [
        json.loads(x.request.content)["text"] for x in slack_request.calls
    ]
    expected_activity_messages = [
        f"New daily Treadmill activity from <@jdoe>:\n    • Distance: {x}"
        for x in scenario.expected_slack_messages
    ]
    assert actual_activity_messages == expected_activity_messages


@contextmanager
def _context(
    custom_conf_yaml: str,
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
):
    """
    Return a context manager with the settings patched with the given custom conf.
    """
    custom_conf_path = tmp_path / "custom-conf.yaml"
    with open(custom_conf_path, "w", encoding="utf-8") as custom_conf_file:
        custom_conf_file.write(custom_conf_yaml)
        custom_conf_file.flush()
        with monkeypatch.context() as mp:
            mp.setenv("SHB_CUSTOM_CONFIG_PATH", str(custom_conf_path))
            settings = Settings(
                app_settings=AppSettings(),
                secret_settings=SecretSettings(),
            )
            with app.container.settings.override(settings):
                yield


async def _log_activities(
    monkeypatch: MonkeyPatch,
    local_fitbit_repository: LocalFitbitRepository,
    fake_now: dt.datetime,
    user: models.User,
    primary_dist_km: float,
    secondary_dist_km: float | None = None,
):
    """
    Log a primary activity and optionally a secondary activity for the given date.

    Create both activities in the database.
    Then call usecase_process_daily_activity, which:
      - Adjusts the credit/debit if necessary
      - Calculates the streak
      - Posts a message to slack.
    """
    await local_fitbit_repository.upsert_activity_for_user(
        user_lookup=HealthUserLookup(user_id=user.fitbit.health_user_id),
        activity=ActivityData(
            log_id=str(uuid.uuid4()),
            type_id=ACTIVITY_TYPE_PRIMARY,
            logged_at=fake_now,
            distance_km=primary_dist_km,
            **DEFAULT_ACTIVITY_ATTRIBUTES,
        ),
    )
    if secondary_dist_km:
        await local_fitbit_repository.upsert_activity_for_user(
            user_lookup=HealthUserLookup(user_id=user.fitbit.health_user_id),
            activity=ActivityData(
                log_id=str(uuid.uuid4()),
                type_id=ACTIVITY_TYPE_SECONDARY,
                logged_at=fake_now,
                distance_km=secondary_dist_km,
                **DEFAULT_ACTIVITY_ATTRIBUTES,
            ),
        )
    with monkeypatch.context() as mp:
        freeze_time(
            mp,
            dt_module_to_freeze=dt_to_freeze,
            frozen_datetime_args=(
                fake_now.year,
                fake_now.month,
                fake_now.day,
                fake_now.hour,
                fake_now.minute,
                fake_now.second,
            ),
        )
        daily_activity = await local_fitbit_repository.get_latest_daily_activity_by_user_and_activity_type(
            user_lookup=HealthUserLookup(user_id=user.fitbit.health_user_id),
            type_id=ACTIVITY_TYPE_PRIMARY,
        )
        await usecase_process_daily_activity.do(
            daily_activity=daily_activity,
            local_fitbit_repo=local_fitbit_repository,
        )

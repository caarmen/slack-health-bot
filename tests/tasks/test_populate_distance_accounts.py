import datetime as dt
import uuid
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from slackhealthbot.data.database import models
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
)
from slackhealthbot.domain.models.activity import ActivityData
from slackhealthbot.domain.models.users import HealthUserLookup
from slackhealthbot.main import app
from slackhealthbot.settings import AppSettings, SecretSettings, Settings
from slackhealthbot.tasks.datamigrations import populate_distance_accounts
from tests.testsupport.factories.factories import FitbitUserFactory, UserFactory

DEFAULT_ACTIVITY_ATTRIBUTES = {
    "total_minutes": 10,
    "calories": 0,
    "zone_minutes": [],
}
ACTIVITY_TYPE_PRIMARY = 90019
ACTIVITY_TYPE_SECONDARY = 90013


@pytest.mark.asyncio
async def test_populate_distance_accounts(
    *,
    monkeypatch: MonkeyPatch,
    user_factory: UserFactory,
    fitbit_user_factory: FitbitUserFactory,
    local_fitbit_repository: LocalFitbitRepository,
):
    """
    Given a user,
    With some primary activities not meeting the goal,
    And some primary activities meeting the goal,
    And some secondary activities,
    When the migration task is run,
    Then a balance exists for the primary activities meeting the goal.
    """

    # Given a user,
    user: models.User = user_factory.create(
        slack_alias="jdoe",
        fitbit=fitbit_user_factory.create(
            health_user_id="123",
        ),
    )
    user_lookup = HealthUserLookup(user_id=user.fitbit.health_user_id)

    # With some primary activities not meeting the goal,
    # And some primary activities meeting the goal,
    # And some secondary activities,
    day1 = dt.datetime(2026, 8, 26, 11, 23, 4)

    activities = [
        # ------------ DAY 1 ------------
        {
            "day": day1,
            "type": ACTIVITY_TYPE_PRIMARY,
            "distance": 18.3,
        },
        {
            "day": day1,
            "type": ACTIVITY_TYPE_SECONDARY,
            "distance": 2.1,
        },
        # ------------ DAY 2 ------------
        {
            "day": day1 + dt.timedelta(days=1),
            "type": ACTIVITY_TYPE_PRIMARY,
            "distance": 18.3,
        },
        # ------------ DAY 3 ------------
        {
            "day": day1 + dt.timedelta(days=2),
            "type": ACTIVITY_TYPE_PRIMARY,
            "distance": 22.7,  # credit of 2.7
        },
        {
            "day": day1 + dt.timedelta(days=2),
            "type": ACTIVITY_TYPE_SECONDARY,
            "distance": 21,
        },
        # ------------ DAY 4 ------------
        {
            "day": day1 + dt.timedelta(days=3),
            "type": ACTIVITY_TYPE_PRIMARY,
            "distance": 20.4,  # credit of 0.4
        },
    ]
    for activity in activities:
        await local_fitbit_repository.upsert_activity_for_user(
            user_lookup=user_lookup,
            activity=ActivityData(
                log_id=str(uuid.uuid4()),
                type_id=activity["type"],
                logged_at=activity["day"],
                distance_km=activity["distance"],
                **DEFAULT_ACTIVITY_ATTRIBUTES,
            ),
        )

    # When the migration task is run,
    with monkeypatch.context() as mp:
        mp.setattr("sys.argv", ["command-name"])
        await populate_distance_accounts.main(container=app.container)

    # Then a balance exists for the primary activities meeting the goal.
    balance = await local_fitbit_repository.get_distance_km_balance_by_user_and_type(
        user_lookup=user_lookup,
        type_id=ACTIVITY_TYPE_PRIMARY,
    )

    assert balance == pytest.approx(3.1)


@pytest.fixture(autouse=True)
def _context(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
):
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
    custom_conf_path = tmp_path / "custom-conf.yaml"
    with open(custom_conf_path, "w", encoding="utf-8") as custom_conf_file:
        custom_conf_file.write(custom_conf)
        custom_conf_file.flush()
        with monkeypatch.context() as mp:
            mp.setenv("SHB_CUSTOM_CONFIG_PATH", str(custom_conf_path))
            settings = Settings(
                app_settings=AppSettings(),
                secret_settings=SecretSettings(),
            )
            with app.container.settings.override(settings):
                yield

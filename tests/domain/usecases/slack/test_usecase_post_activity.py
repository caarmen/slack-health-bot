import dataclasses
import re
from pathlib import Path

import pytest

from slackhealthbot.domain.models.activity import (
    ActivityData,
    ActivityHistory,
    ActivityZone,
    ActivityZoneMinutes,
    TopActivityStats,
)
from slackhealthbot.domain.usecases.slack import usecase_post_activity
from slackhealthbot.main import app
from slackhealthbot.settings import AppSettings, SecretSettings, Settings


@pytest.mark.parametrize(
    [
        "input_value",
        "input_all_time_top_value",
        "input_recent_top_value",
        "expected_output",
    ],
    [
        (12, 14, 13, ""),
        (13, 14, 13, "New record (last 2 days)! 🏆"),
        (13, 13, 13, "New all-time record! 🏆"),
    ],
)
def test_get_ranking_text(
    input_value: int,
    input_all_time_top_value: int,
    input_recent_top_value: int,
    expected_output: str,
):
    actual_output = usecase_post_activity.get_ranking_text(
        input_value,
        input_all_time_top_value,
        input_recent_top_value,
        record_history_days=2,
    )
    assert actual_output == expected_output


@dataclasses.dataclass
class CreateMessageScenario:
    name: str
    new_activity_data: ActivityData
    expected_message_regex: str


CREATE_MESSAGE_SCENARIOS = [
    CreateMessageScenario(
        name="new all-time record",
        new_activity_data=ActivityData(
            log_id=-3,
            type_id=123,
            total_minutes=120,
            calories=315,
            distance_km=10.2,
            zone_minutes=[
                ActivityZoneMinutes(
                    zone=ActivityZone.CARDIO,
                    minutes=120,
                ),
                ActivityZoneMinutes(
                    zone=ActivityZone.FAT_BURN,
                    minutes=60,
                ),
            ],
        ),
        expected_message_regex="^.* New all-time record! 🏆.* New all-time record! 🏆.* New all-time record! "
        "🏆.* New all-time record! 🏆.* New all-time record! 🏆$",
    ),
    CreateMessageScenario(
        name="recent top record",
        new_activity_data=ActivityData(
            log_id=-3,
            type_id=123,
            total_minutes=90,
            calories=175,
            distance_km=8.1,
            zone_minutes=[
                ActivityZoneMinutes(
                    zone=ActivityZone.CARDIO,
                    minutes=50,
                ),
                ActivityZoneMinutes(
                    zone=ActivityZone.FAT_BURN,
                    minutes=25,
                ),
            ],
        ),
        expected_message_regex="^.* New record \\(last 30 days\\)! 🏆.* New record \\(last 30 days\\)! 🏆.* New record \\(last 30 days\\)! 🏆.* New "
        "record \\(last 30 days\\)! 🏆.* New record \\(last 30 days\\)! 🏆$",
    ),
    CreateMessageScenario(
        name="lowest score",
        new_activity_data=ActivityData(
            log_id=-3,
            type_id=123,
            total_minutes=1,
            calories=1,
            distance_km=0.1,
            zone_minutes=[
                ActivityZoneMinutes(
                    zone=ActivityZone.CARDIO,
                    minutes=1,
                ),
                ActivityZoneMinutes(
                    zone=ActivityZone.FAT_BURN,
                    minutes=1,
                ),
            ],
        ),
        expected_message_regex=r"^((?!🏆).)*$",
    ),
]


@pytest.mark.parametrize(
    ids=[x.name for x in CREATE_MESSAGE_SCENARIOS],
    argnames=["scenario"],
    argvalues=[[x] for x in CREATE_MESSAGE_SCENARIOS],
)
def test_create_message(scenario: CreateMessageScenario):
    activity_history = ActivityHistory(
        new_activity_data=scenario.new_activity_data,
        all_time_top_activity_data=TopActivityStats(
            top_total_minutes=100,
            top_calories=215,
            top_distance_km=9.0,
            top_zone_minutes=[
                ActivityZoneMinutes(
                    zone=ActivityZone.CARDIO,
                    minutes=60,
                ),
                ActivityZoneMinutes(
                    zone=ActivityZone.FAT_BURN,
                    minutes=40,
                ),
            ],
        ),
        recent_top_activity_data=TopActivityStats(
            top_total_minutes=90,
            top_calories=175,
            top_distance_km=8.1,
            top_zone_minutes=[
                ActivityZoneMinutes(
                    zone=ActivityZone.CARDIO,
                    minutes=50,
                ),
                ActivityZoneMinutes(
                    zone=ActivityZone.FAT_BURN,
                    minutes=25,
                ),
            ],
        ),
    )
    actual_message = usecase_post_activity.create_message(
        slack_alias="somebody",
        activity_name="Dancing",
        activity_history=activity_history,
        record_history_days=30,
    )
    assert re.search(scenario.expected_message_regex, actual_message.replace("\n", ""))


@dataclasses.dataclass
class CreateMessageReportFieldsScenario:
    name: str
    custom_conf: str
    expected_message: str


CREATE_MESSAGE_REPORT_FIELDS_SCENARIOS = [
    CreateMessageReportFieldsScenario(
        name="no custom conf",
        custom_conf=None,
        expected_message="""
New Dancing activity from <@somebody>:
    • Duration: 90 minutes New record (last 30 days)! 🏆
    • Calories: 175 New record (last 30 days)! 🏆
    • Distance: 8.100 km New record (last 30 days)! 🏆
    • Cardio minutes: 50 New record (last 30 days)! 🏆
    • Fat burn minutes: 25 New record (last 30 days)! 🏆""",
    ),
    CreateMessageReportFieldsScenario(
        name="distance only",
        custom_conf="""
fitbit:
  activities:
    activity_types:
      - name: Dancing
        id: 123
        report:
          daily: true
          realtime: false
          fields:
            - distance
""",
        expected_message="""
New Dancing activity from <@somebody>:
    • Distance: 8.100 km New record (last 30 days)! 🏆
""",
    ),
    CreateMessageReportFieldsScenario(
        name="custom conf not overriding report values",
        custom_conf="""
fitbit:
  activities:
    activity_types:
      - name: Dancing
        id: 123
""",
        expected_message="""
New Dancing activity from <@somebody>:
    • Duration: 90 minutes New record (last 30 days)! 🏆
    • Calories: 175 New record (last 30 days)! 🏆
    • Distance: 8.100 km New record (last 30 days)! 🏆
    • Cardio minutes: 50 New record (last 30 days)! 🏆
    • Fat burn minutes: 25 New record (last 30 days)! 🏆""",
    ),
]


@pytest.mark.parametrize(
    ids=[x.name for x in CREATE_MESSAGE_REPORT_FIELDS_SCENARIOS],
    argnames="scenario",
    argvalues=CREATE_MESSAGE_REPORT_FIELDS_SCENARIOS,
)
def test_create_message_report_fields(
    scenario: CreateMessageReportFieldsScenario,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    settings: Settings,
):
    if scenario.custom_conf:
        custom_conf_path = tmp_path / "custom-conf.yaml"
        with open(custom_conf_path, "w", encoding="utf-8") as custom_conf_file:
            custom_conf_file.write(scenario.custom_conf)
        with monkeypatch.context() as mp:
            mp.setenv("SHB_CUSTOM_CONFIG_PATH", str(custom_conf_path))
            settings = Settings(
                app_settings=AppSettings(),
                secret_settings=SecretSettings(),
            )
    new_activity_data = ActivityData(
        log_id=-3,
        type_id=123,
        total_minutes=90,
        calories=175,
        distance_km=8.1,
        zone_minutes=[
            ActivityZoneMinutes(
                zone=ActivityZone.CARDIO,
                minutes=50,
            ),
            ActivityZoneMinutes(
                zone=ActivityZone.FAT_BURN,
                minutes=25,
            ),
        ],
    )
    activity_history = ActivityHistory(
        new_activity_data=new_activity_data,
        all_time_top_activity_data=TopActivityStats(
            top_total_minutes=100,
            top_calories=215,
            top_distance_km=9.0,
            top_zone_minutes=[
                ActivityZoneMinutes(
                    zone=ActivityZone.CARDIO,
                    minutes=60,
                ),
                ActivityZoneMinutes(
                    zone=ActivityZone.FAT_BURN,
                    minutes=40,
                ),
            ],
        ),
        recent_top_activity_data=TopActivityStats(
            top_total_minutes=90,
            top_calories=175,
            top_distance_km=8.1,
            top_zone_minutes=[
                ActivityZoneMinutes(
                    zone=ActivityZone.CARDIO,
                    minutes=50,
                ),
                ActivityZoneMinutes(
                    zone=ActivityZone.FAT_BURN,
                    minutes=25,
                ),
            ],
        ),
    )
    with app.container.settings.override(settings):
        actual_message = usecase_post_activity.create_message(
            slack_alias="somebody",
            activity_name="Dancing",
            activity_history=activity_history,
            record_history_days=30,
        )
    assert actual_message == scenario.expected_message

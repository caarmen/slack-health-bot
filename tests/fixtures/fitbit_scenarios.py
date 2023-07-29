import dataclasses
import datetime
from typing import Any

from slackhealthbot.services.models import SleepData


@dataclasses.dataclass
class FitbitSleepScenario:
    input_initial_sleep_data: dict[str, int]
    input_mock_fitbit_response: dict[str, Any]
    expected_new_last_sleep_data: SleepData
    expected_icons: str


sleep_scenarios: dict[str, FitbitSleepScenario] = {
    "No previous sleep data": FitbitSleepScenario(
        # No previous sleep data
        input_initial_sleep_data={
            "last_sleep_start_time": None,
            "last_sleep_end_time": None,
            "last_sleep_sleep_minutes": None,
            "last_sleep_wake_minutes": None,
        },
        input_mock_fitbit_response={
            "sleep": [
                {
                    "endTime": "2023-05-13T09:27:30.000",
                    "duration": 31620000,
                    "startTime": "2023-05-13T00:40:00.000",
                    "type": "stages",
                    "isMainSleep": True,
                    "levels": {
                        "summary": {"wake": {"minutes": 32}},
                    },
                },
            ]
        },
        expected_new_last_sleep_data=SleepData(
            start_time=datetime.datetime(2023, 5, 13, 0, 40, 0),
            end_time=datetime.datetime(2023, 5, 13, 9, 27, 30),
            sleep_minutes=495,
            wake_minutes=32,
        ),
        expected_icons="",
    ),
    "New sleep data higher": FitbitSleepScenario(
        # Previous sleep data exists.
        # Newer values are all higher than previous values
        input_initial_sleep_data={
            "last_sleep_start_time": datetime.datetime(2023, 5, 11, 23, 39, 0),
            "last_sleep_end_time": datetime.datetime(2023, 5, 12, 8, 28, 0),
            "last_sleep_sleep_minutes": 449,
            "last_sleep_wake_minutes": 80,
        },
        input_mock_fitbit_response={
            "sleep": [
                {
                    "startTime": "2023-05-13T00:40:00.000",
                    "endTime": "2023-05-13T09:27:30.000",
                    "duration": 31620000,
                    "type": "classic",
                    "isMainSleep": True,
                    "levels": {
                        "summary": {
                            "asleep": {"minutes": 495},
                            "awake": {"minutes": 130},
                        },
                    },
                },
            ]
        },
        expected_new_last_sleep_data=SleepData(
            start_time=datetime.datetime(2023, 5, 13, 0, 40, 0),
            end_time=datetime.datetime(2023, 5, 13, 9, 27, 30),
            sleep_minutes=495,
            wake_minutes=130,
        ),
        expected_icons="⬆️.*⬆️.*⬆️.*⬆️",
    ),
    "New sleep data slightly higher": FitbitSleepScenario(
        # Previous sleep data exists.
        # Newer values are all slightly higher than previous values
        input_initial_sleep_data={
            "last_sleep_start_time": datetime.datetime(2023, 5, 12, 0, 5, 0),
            "last_sleep_end_time": datetime.datetime(2023, 5, 12, 9, 0, 0),
            "last_sleep_sleep_minutes": 460,
            "last_sleep_wake_minutes": 16,
        },
        input_mock_fitbit_response={
            "sleep": [
                {
                    "startTime": "2023-05-13T00:40:00.000",
                    "endTime": "2023-05-13T09:27:30.000",
                    "duration": 32700000,
                    "type": "stages",
                    "isMainSleep": True,
                    "levels": {
                        "summary": {"wake": {"minutes": 50}},
                    },
                },
            ]
        },
        expected_new_last_sleep_data=SleepData(
            start_time=datetime.datetime(2023, 5, 13, 0, 40, 0),
            end_time=datetime.datetime(2023, 5, 13, 9, 27, 30),
            sleep_minutes=495,
            wake_minutes=50,
        ),
        expected_icons="↗️.*↗️.*↗️.*↗️",
    ),
    "New sleep data barely higher": FitbitSleepScenario(
        # Previous sleep data exists.
        # Newer values are all barely higher than previous values
        input_initial_sleep_data={
            "last_sleep_start_time": datetime.datetime(2023, 5, 12, 0, 39, 0),
            "last_sleep_end_time": datetime.datetime(2023, 5, 12, 9, 25, 0),
            "last_sleep_sleep_minutes": 490,
            "last_sleep_wake_minutes": 45,
        },
        input_mock_fitbit_response={
            "sleep": [
                {
                    "startTime": "2023-05-13T00:40:00.000",
                    "endTime": "2023-05-13T09:27:30.000",
                    "duration": 31620000,
                    "type": "classic",
                    "isMainSleep": True,
                    "levels": {
                        "summary": {
                            "asleep": {"minutes": 495},
                            "awake": {"minutes": 50},
                        },
                    },
                },
            ]
        },
        expected_new_last_sleep_data=SleepData(
            start_time=datetime.datetime(2023, 5, 13, 0, 40, 0),
            end_time=datetime.datetime(2023, 5, 13, 9, 27, 30),
            sleep_minutes=495,
            wake_minutes=50,
        ),
        expected_icons="➡️.*➡️.*➡️.*➡️",
    ),
    "New sleep data barely lower": FitbitSleepScenario(
        # Previous sleep data exists.
        # Newer values are all barely lower than previous values
        input_initial_sleep_data={
            "last_sleep_start_time": datetime.datetime(2023, 5, 12, 0, 41, 0),
            "last_sleep_end_time": datetime.datetime(2023, 5, 12, 9, 28, 0),
            "last_sleep_sleep_minutes": 500,
            "last_sleep_wake_minutes": 51,
        },
        input_mock_fitbit_response={
            "sleep": [
                {
                    "startTime": "2023-05-13T00:40:00.000",
                    "endTime": "2023-05-13T09:27:30.000",
                    "duration": 31620000,
                    "type": "classic",
                    "isMainSleep": True,
                    "levels": {
                        "summary": {
                            "asleep": {"minutes": 495},
                            "awake": {"minutes": 50},
                        },
                    },
                },
            ]
        },
        expected_new_last_sleep_data=SleepData(
            start_time=datetime.datetime(2023, 5, 13, 0, 40, 0),
            end_time=datetime.datetime(2023, 5, 13, 9, 27, 30),
            sleep_minutes=495,
            wake_minutes=50,
        ),
        expected_icons="➡️.*➡️.*➡️.*➡️",
    ),
    "New sleep data slightly lower": FitbitSleepScenario(
        # Previous sleep data exists.
        # Newer values are all slightly lower than previous values
        input_initial_sleep_data={
            "last_sleep_start_time": datetime.datetime(2023, 5, 12, 1, 15, 0),
            "last_sleep_end_time": datetime.datetime(2023, 5, 12, 10, 11, 0),
            "last_sleep_sleep_minutes": 539,
            "last_sleep_wake_minutes": 80,
        },
        input_mock_fitbit_response={
            "sleep": [
                {
                    "startTime": "2023-05-13T00:40:00.000",
                    "endTime": "2023-05-13T09:27:30.000",
                    "duration": 31620000,
                    "type": "classic",
                    "isMainSleep": True,
                    "levels": {
                        "summary": {
                            "asleep": {"minutes": 495},
                            "awake": {"minutes": 50},
                        },
                    },
                },
            ]
        },
        expected_new_last_sleep_data=SleepData(
            start_time=datetime.datetime(2023, 5, 13, 0, 40, 0),
            end_time=datetime.datetime(2023, 5, 13, 9, 27, 30),
            sleep_minutes=495,
            wake_minutes=50,
        ),
        expected_icons="↘️.*↘️.*↘️.*↘️",
    ),
    "New sleep data lower": FitbitSleepScenario(
        # Previous sleep data exists.
        # Newer values are all lower than previous values
        input_initial_sleep_data={
            "last_sleep_start_time": datetime.datetime(2023, 5, 12, 1, 41, 0),
            "last_sleep_end_time": datetime.datetime(2023, 5, 12, 10, 28, 0),
            "last_sleep_sleep_minutes": 560,
            "last_sleep_wake_minutes": 200,
        },
        input_mock_fitbit_response={
            "sleep": [
                {
                    "startTime": "2023-05-13T00:40:00.000",
                    "endTime": "2023-05-13T09:27:30.000",
                    "duration": 31620000,
                    "type": "classic",
                    "isMainSleep": True,
                    "levels": {
                        "summary": {
                            "asleep": {"minutes": 495},
                            "awake": {"minutes": 130},
                        },
                    },
                },
            ]
        },
        expected_new_last_sleep_data=SleepData(
            start_time=datetime.datetime(2023, 5, 13, 0, 40, 0),
            end_time=datetime.datetime(2023, 5, 13, 9, 27, 30),
            sleep_minutes=495,
            wake_minutes=130,
        ),
        expected_icons="⬇️.*⬇️.*⬇️.*⬇️",
    ),
}

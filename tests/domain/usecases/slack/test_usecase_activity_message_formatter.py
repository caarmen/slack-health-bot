import pytest

from slackhealthbot.domain.usecases.slack import usecase_activity_message_formatter


@pytest.mark.parametrize(
    [
        "input_value",
        "expected_output",
    ],
    [
        (0, "➡️"),
        (1, "➡️"),
        (-1, "➡️"),
        (100, "⬆️"),
        (-100, "⬇️"),
        (5, "↗️"),
        (-5, "↘️"),
    ],
)
def test_get_activity_minutes_change_icon(
    input_value: int,
    expected_output: str,
):
    actual_output = usecase_activity_message_formatter.get_activity_minutes_change_icon(
        input_value
    )
    assert actual_output == expected_output


@pytest.mark.parametrize(
    [
        "input_value",
        "expected_output",
    ],
    [
        (0, "➡️"),
        (1, "➡️"),
        (-1, "➡️"),
        (100, "⬆️"),
        (-100, "⬇️"),
        (35, "↗️"),
        (-35, "↘️"),
    ],
)
def test_get_activity_calories_change_icon(
    input_value: int,
    expected_output: str,
):
    actual_output = (
        usecase_activity_message_formatter.get_activity_calories_change_icon(
            input_value
        )
    )
    assert actual_output == expected_output


@pytest.mark.parametrize(
    [
        "input_value",
        "expected_output",
    ],
    [
        (0, "➡️"),
        (1, "➡️"),
        (-1, "➡️"),
        (30, "⬆️"),
        (-30, "⬇️"),
        (20, "↗️"),
        (-20, "↘️"),
    ],
)
def test_get_activity_distance_km_change_icon(
    input_value: int,
    expected_output: str,
):
    actual_output = (
        usecase_activity_message_formatter.get_activity_distance_km_change_icon(
            distance_km_change_pct=input_value
        )
    )
    assert actual_output == expected_output

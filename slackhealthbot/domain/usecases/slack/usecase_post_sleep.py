import datetime

from dependency_injector.wiring import Provide, inject

from slackhealthbot.containers import Container
from slackhealthbot.domain.models.sleep import SleepData
from slackhealthbot.domain.remoterepository.remoteslackrepository import (
    RemoteSlackRepository,
)


@inject
async def do(
    slack_alias: str,
    new_sleep_data: SleepData,
    last_sleep_data: SleepData,
    slack_repo: RemoteSlackRepository = Provide[Container.slack_repository],
):
    message = create_message(
        slack_alias=slack_alias,
        new_sleep_data=new_sleep_data,
        last_sleep_data=last_sleep_data,
    )
    await slack_repo.post_message(message)


def create_message(
    slack_alias: str,
    new_sleep_data: SleepData,
    last_sleep_data: SleepData,
):
    if last_sleep_data:
        start_time_icon = get_datetime_change_icon(
            last_datetime=last_sleep_data.start_time,
            new_datetime=new_sleep_data.start_time,
        )
        end_time_icon = get_datetime_change_icon(
            last_datetime=last_sleep_data.end_time,
            new_datetime=new_sleep_data.end_time,
        )
        sleep_minutes_icon = get_seconds_change_icon(
            (new_sleep_data.sleep_minutes - last_sleep_data.sleep_minutes) * 60
        )
        wake_minutes_icon = get_seconds_change_icon(
            (new_sleep_data.wake_minutes - last_sleep_data.wake_minutes) * 60
        )
    else:
        start_time_icon = end_time_icon = sleep_minutes_icon = wake_minutes_icon = ""

    return f"""
    New sleep from <@{slack_alias}>: 
    • Went to bed at {format_time(new_sleep_data.start_time)} {start_time_icon}
    • Woke up at {format_time(new_sleep_data.end_time)} {end_time_icon}
    • Total sleep: {format_minutes(new_sleep_data.sleep_minutes)} {sleep_minutes_icon}
    • Awake: {format_minutes(new_sleep_data.wake_minutes)} {wake_minutes_icon}
    """.strip()


def get_datetime_change_icon(
    last_datetime: datetime.datetime, new_datetime: datetime.datetime
) -> str:
    if last_datetime == new_datetime:
        return "➡️"

    fake_last_datetime = last_datetime + datetime.timedelta(days=1)
    time_diff_seconds = int((new_datetime - fake_last_datetime).total_seconds())
    return get_seconds_change_icon(time_diff_seconds)


SLEEP_TIME_SECONDS_CHANGE_SMALL = 15 * 60
SLEEP_TIME_SECONDS_CHANGE_LARGE = 45 * 60


def get_seconds_change_icon(seconds_change: int) -> str:
    if seconds_change > SLEEP_TIME_SECONDS_CHANGE_LARGE:
        return "⬆️"
    if seconds_change > SLEEP_TIME_SECONDS_CHANGE_SMALL:
        return "↗️"
    if seconds_change < -SLEEP_TIME_SECONDS_CHANGE_LARGE:
        return "⬇️"
    if seconds_change < -SLEEP_TIME_SECONDS_CHANGE_SMALL:
        return "↘️"
    return "➡️"


def format_time(dt: datetime.datetime) -> str:
    return dt.strftime("%-H:%M")


def format_minutes(total_minutes: int) -> str:
    hours, minutes_remainder = divmod(total_minutes, 60)
    return f"{hours}h {minutes_remainder}m" if hours else f"{minutes_remainder}m"

from dependency_injector.wiring import Provide, inject

from slackhealthbot.containers import Container
from slackhealthbot.domain.models.activity import ActivityHistory
from slackhealthbot.domain.remoterepository.remoteslackrepository import (
    RemoteSlackRepository,
)
from slackhealthbot.domain.usecases.slack.usecase_activity_message_formatter import (
    format_activity_zone,
    get_ranking_text,
)
from slackhealthbot.settings import ReportField, Settings


@inject
async def do(
    slack_alias: str,
    activity_name: str,
    activity_history: ActivityHistory,
    record_history_days: int,
    slack_repo: RemoteSlackRepository = Provide[Container.slack_repository],
):
    message = create_message(
        slack_alias, activity_name, activity_history, record_history_days
    )
    await slack_repo.post_message(message.strip())


@inject
def create_message(
    slack_alias: str,
    activity_name: str,
    activity_history: ActivityHistory,
    record_history_days: int,
    settings: Settings = Provide[Container.settings],
):
    activity = activity_history.new_activity_data
    zone_record_texts = {}
    duration_record_text = get_ranking_text(
        activity.total_minutes,
        activity_history.all_time_top_activity_data.top_total_minutes,
        activity_history.recent_top_activity_data.top_total_minutes,
        record_history_days=record_history_days,
    )
    calories_record_text = get_ranking_text(
        activity.calories,
        activity_history.all_time_top_activity_data.top_calories,
        activity_history.recent_top_activity_data.top_calories,
        record_history_days=record_history_days,
    )
    distance_km_record_text = (
        get_ranking_text(
            activity.distance_km,
            activity_history.all_time_top_activity_data.top_distance_km,
            activity_history.recent_top_activity_data.top_distance_km,
            record_history_days=record_history_days,
        )
        if activity.distance_km
        else None
    )

    for zone_minutes in activity.zone_minutes:
        all_time_top_value = next(
            (
                x.minutes
                for x in activity_history.all_time_top_activity_data.top_zone_minutes
                if x.zone == zone_minutes.zone
            ),
            0,
        )
        recent_top_value = next(
            (
                x.minutes
                for x in activity_history.recent_top_activity_data.top_zone_minutes
                if x.zone == zone_minutes.zone
            ),
            0,
        )
        zone_record_texts[zone_minutes.zone] = get_ranking_text(
            zone_minutes.minutes,
            all_time_top_value,
            recent_top_value,
            record_history_days=record_history_days,
        )
    report_settings = settings.app_settings.fitbit.activities.get_report(
        activity_type_id=activity_history.new_activity_data.type_id
    )

    message = f"""
New {activity_name} activity from <@{slack_alias}>:
"""

    if ReportField.duration in report_settings.fields:
        message += f"""    • Duration: {activity.total_minutes} minutes {duration_record_text}
"""

    if ReportField.calories in report_settings.fields:
        message += f"""    • Calories: {activity.calories} {calories_record_text}
"""

    if ReportField.distance in report_settings.fields and activity.distance_km:
        message += f"""    • Distance: {activity.distance_km:.3f} km {distance_km_record_text}
"""
    message += "\n".join(
        [
            f"    • {format_activity_zone(zone_minutes.zone)}"
            + f" minutes: {zone_minutes.minutes}"
            + (
                f" {zone_record_texts.get(zone_minutes.zone, '')}"
                if zone_record_texts.get(zone_minutes.zone)
                else ""
            )
            for zone_minutes in activity.zone_minutes
            if f"{zone_minutes.zone}_minutes" in report_settings.fields
        ]
    )
    return message

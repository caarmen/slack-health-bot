from slackhealthbot.domain.models.activity import ActivityHistory, ActivityZone
from slackhealthbot.domain.remoterepository.remoteslackrepository import (
    RemoteSlackRepository,
)


async def do(
    repo: RemoteSlackRepository,
    slack_alias: str,
    activity_name: str,
    activity_history: ActivityHistory,
    record_history_days: int,
):
    message = create_message(
        slack_alias, activity_name, activity_history, record_history_days
    )
    await repo.post_message(message.strip())


def create_message(
    slack_alias: str,
    activity_name: str,
    activity_history: ActivityHistory,
    record_history_days: int,
):
    activity = activity_history.new_activity_data
    zone_icons = {}
    zone_record_texts = {}
    if activity_history.latest_activity_data:
        duration_icon = get_activity_minutes_change_icon(
            activity.total_minutes
            - activity_history.latest_activity_data.total_minutes,
        )
        calories_icon = get_activity_calories_change_icon(
            activity.calories - activity_history.latest_activity_data.calories,
        )
        distance_km_icon = (
            get_activity_distance_km_change_icon(
                (
                    activity.distance_km
                    - activity_history.latest_activity_data.distance_km
                )
                * 100
                / activity.distance_km,
            )
            if activity.distance_km
            and activity_history.latest_activity_data.distance_km
            else ""
        )

        for zone_minutes in activity.zone_minutes:
            last_zone_minutes = next(
                (
                    x.minutes
                    for x in activity_history.latest_activity_data.zone_minutes
                    if x.zone == zone_minutes.zone
                ),
                0,
            )
            zone_icons[zone_minutes.zone] = get_activity_minutes_change_icon(
                zone_minutes.minutes - last_zone_minutes
            )

    else:
        duration_icon = calories_icon = distance_km_icon = ""
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
    message = f"""
New {activity_name} activity from <@{slack_alias}>:
    • Duration: {activity.total_minutes} minutes {duration_icon} {duration_record_text}
    • Calories: {activity.calories} {calories_icon} {calories_record_text}
"""
    if activity.distance_km:
        message += f"""    • Distance: {activity.distance_km:.3f} km {distance_km_icon} {distance_km_record_text}
"""
    message += "\n".join(
        [
            f"    • {format_activity_zone(zone_minutes.zone)}"
            + f" minutes: {zone_minutes.minutes} "
            + zone_icons.get(zone_minutes.zone, "")
            + f" {zone_record_texts.get(zone_minutes.zone, '')}"
            for zone_minutes in activity.zone_minutes
        ]
    )
    return message


def format_activity_zone(activity_zone: ActivityZone) -> str:
    return activity_zone.capitalize().replace("_", " ")


ACTIVITY_DURATION_MINUTES_CHANGE_SMALL = 2
ACTIVITY_DURATION_MINUTES_CHANGE_LARGE = 10


def get_activity_minutes_change_icon(minutes_change: int) -> str:
    if minutes_change > ACTIVITY_DURATION_MINUTES_CHANGE_LARGE:
        return "⬆️"
    if minutes_change > ACTIVITY_DURATION_MINUTES_CHANGE_SMALL:
        return "↗️"
    if minutes_change < -ACTIVITY_DURATION_MINUTES_CHANGE_LARGE:
        return "⬇️"
    if minutes_change < -ACTIVITY_DURATION_MINUTES_CHANGE_SMALL:
        return "↘️"
    return "➡️"


CALORIES_CHANGE_SMALL = 25
CALORIES_CHANGE_LARGE = 50


def get_activity_calories_change_icon(calories_change: int) -> str:
    if calories_change > CALORIES_CHANGE_LARGE:
        return "⬆️"
    if calories_change > CALORIES_CHANGE_SMALL:
        return "↗️"
    if calories_change < -CALORIES_CHANGE_LARGE:
        return "⬇️"
    if calories_change < -CALORIES_CHANGE_SMALL:
        return "↘️"
    return "➡️"


DISTANCE_CHANGE_PCT_SMALL = 15
DISTANCE_CHANGE_PCT_LARGE = 25


def get_activity_distance_km_change_icon(distance_km_change_pct: int) -> str:
    if distance_km_change_pct > DISTANCE_CHANGE_PCT_LARGE:
        return "⬆️"
    if distance_km_change_pct > DISTANCE_CHANGE_PCT_SMALL:
        return "↗️"
    if distance_km_change_pct < -DISTANCE_CHANGE_PCT_LARGE:
        return "⬇️"
    if distance_km_change_pct < -DISTANCE_CHANGE_PCT_SMALL:
        return "↘️"
    return "➡️"


def get_ranking_text(
    value: int,
    all_time_top_value: int,
    recent_top_value: int,
    record_history_days: int,
) -> str:
    if value >= all_time_top_value:
        return "New all-time record! 🏆"
    if value >= recent_top_value:
        return f"New record (last {record_history_days} days)! 🏆"
    return ""

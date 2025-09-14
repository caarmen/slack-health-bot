from dependency_injector.wiring import Provide, inject

from slackhealthbot.containers import Container
from slackhealthbot.domain.models.activity import DailyActivityHistory
from slackhealthbot.domain.remoterepository.remoteopenairepository import (
    RemoteOpenAiRepository,
)
from slackhealthbot.domain.remoterepository.remoteslackrepository import (
    RemoteSlackRepository,
)
from slackhealthbot.domain.usecases.slack.usecase_activity_message_formatter import (
    get_activity_calories_change_icon,
    get_activity_distance_km_change_icon,
    get_activity_minutes_change_icon,
    get_ranking_text,
)
from slackhealthbot.settings import Report, ReportField, Settings


@inject
async def do(
    slack_alias: str,
    activity_name: str,
    history: DailyActivityHistory,
    record_history_days: int,
    slack_repo: RemoteSlackRepository = Provide[Container.slack_repository],
):
    message = await create_message(
        slack_alias=slack_alias,
        activity_name=activity_name,
        history=history,
        record_history_days=record_history_days,
    )
    await slack_repo.post_message(message.strip())


@inject
async def create_message(
    slack_alias: str,
    activity_name: str,
    history: DailyActivityHistory,
    record_history_days: int,
    settings: Settings = Provide[Container.settings],
) -> str:
    if history.previous_daily_activity_stats:
        calories_icon = (
            get_activity_calories_change_icon(
                history.new_daily_activity_stats.sum_calories
                - history.previous_daily_activity_stats.sum_calories
            )
            if history.previous_daily_activity_stats.sum_calories
            else ""
        )
        distance_km_icon = (
            get_activity_distance_km_change_icon(
                (
                    history.new_daily_activity_stats.sum_distance_km
                    - history.previous_daily_activity_stats.sum_distance_km
                )
                * 100
                / history.new_daily_activity_stats.sum_distance_km,
            )
            if history.new_daily_activity_stats.sum_distance_km
            and history.previous_daily_activity_stats.sum_distance_km
            else ""
        )
        total_minutes_icon = get_activity_minutes_change_icon(
            history.new_daily_activity_stats.sum_total_minutes
            - history.previous_daily_activity_stats.sum_total_minutes,
        )
        fat_burn_minutes_icon = (
            get_activity_minutes_change_icon(
                history.new_daily_activity_stats.sum_fat_burn_minutes
                - history.previous_daily_activity_stats.sum_fat_burn_minutes,
            )
            if history.new_daily_activity_stats.sum_fat_burn_minutes
            and history.previous_daily_activity_stats.sum_fat_burn_minutes
            else ""
        )
        cardio_minutes_icon = (
            get_activity_minutes_change_icon(
                history.new_daily_activity_stats.sum_cardio_minutes
                - history.previous_daily_activity_stats.sum_cardio_minutes,
            )
            if history.new_daily_activity_stats.sum_cardio_minutes
            and history.previous_daily_activity_stats.sum_cardio_minutes
            else ""
        )
        peak_minutes_icon = (
            get_activity_minutes_change_icon(
                history.new_daily_activity_stats.sum_peak_minutes
                - history.previous_daily_activity_stats.sum_peak_minutes,
            )
            if history.new_daily_activity_stats.sum_peak_minutes
            and history.previous_daily_activity_stats.sum_peak_minutes
            else ""
        )
        out_of_zone_minutes_icon = (
            get_activity_minutes_change_icon(
                history.new_daily_activity_stats.sum_out_of_zone_minutes
                - history.previous_daily_activity_stats.sum_out_of_zone_minutes,
            )
            if history.new_daily_activity_stats.sum_out_of_zone_minutes
            and history.previous_daily_activity_stats.sum_out_of_zone_minutes
            else ""
        )
    else:
        calories_icon = distance_km_icon = total_minutes_icon = (
            fat_burn_minutes_icon
        ) = cardio_minutes_icon = peak_minutes_icon = out_of_zone_minutes_icon = ""

    calories_record_text = get_ranking_text(
        history.new_daily_activity_stats.sum_calories,
        history.all_time_top_daily_activity_stats.top_sum_calories,
        history.recent_top_daily_activity_stats.top_sum_calories,
        record_history_days=record_history_days,
    )

    distance_km_record_text = get_ranking_text(
        history.new_daily_activity_stats.sum_distance_km,
        history.all_time_top_daily_activity_stats.top_sum_distance_km,
        history.recent_top_daily_activity_stats.top_sum_distance_km,
        record_history_days=record_history_days,
    )

    total_minutes_record_text = get_ranking_text(
        history.new_daily_activity_stats.sum_total_minutes,
        history.all_time_top_daily_activity_stats.top_sum_total_minutes,
        history.recent_top_daily_activity_stats.top_sum_total_minutes,
        record_history_days=record_history_days,
    )

    fat_burn_minutes_record_text = get_ranking_text(
        history.new_daily_activity_stats.sum_fat_burn_minutes,
        history.all_time_top_daily_activity_stats.top_sum_fat_burn_minutes,
        history.recent_top_daily_activity_stats.top_sum_fat_burn_minutes,
        record_history_days=record_history_days,
    )

    cardio_minutes_record_text = get_ranking_text(
        history.new_daily_activity_stats.sum_cardio_minutes,
        history.all_time_top_daily_activity_stats.top_sum_cardio_minutes,
        history.recent_top_daily_activity_stats.top_sum_cardio_minutes,
        record_history_days=record_history_days,
    )

    peak_minutes_record_text = get_ranking_text(
        history.new_daily_activity_stats.sum_peak_minutes,
        history.all_time_top_daily_activity_stats.top_sum_peak_minutes,
        history.recent_top_daily_activity_stats.top_sum_peak_minutes,
        record_history_days=record_history_days,
    )

    out_of_zone_minutes_record_text = get_ranking_text(
        history.new_daily_activity_stats.sum_out_of_zone_minutes,
        history.all_time_top_daily_activity_stats.top_sum_out_of_zone_minutes,
        history.recent_top_daily_activity_stats.top_sum_out_of_zone_minutes,
        record_history_days=record_history_days,
    )

    report_settings = settings.app_settings.fitbit.activities.get_report(
        activity_type_id=history.new_daily_activity_stats.type_id
    )

    message = f"""
New daily {activity_name} activity from <@{slack_alias}>:
"""

    if ReportField.activity_count in report_settings.fields:
        message += f"""    • Activity count: {history.new_daily_activity_stats.count_activities}
"""

    if ReportField.duration in report_settings.fields:
        message += f"""    • Total duration: {history.new_daily_activity_stats.sum_total_minutes} minutes {total_minutes_icon} {total_minutes_record_text}
"""

    if ReportField.calories in report_settings.fields:
        message += f"""    • Total calories: {history.new_daily_activity_stats.sum_calories} {calories_icon} {calories_record_text}
"""
    if (
        ReportField.distance in report_settings.fields
        and history.new_daily_activity_stats.sum_distance_km
    ):
        message += f"    • Distance: {history.new_daily_activity_stats.sum_distance_km:.3f} km {distance_km_icon} {distance_km_record_text}"
        message += await create_motivational_message(
            slack_alias=slack_alias,
            activity_name=activity_name,
            report_settings=report_settings,
            history=history,
        )

    if (
        ReportField.fat_burn_minutes in report_settings.fields
        and history.new_daily_activity_stats.sum_fat_burn_minutes
    ):
        message += f"""    • Total fat burn minutes: {history.new_daily_activity_stats.sum_fat_burn_minutes} {fat_burn_minutes_icon} {fat_burn_minutes_record_text}
"""
    if (
        ReportField.cardio_minutes in report_settings.fields
        and history.new_daily_activity_stats.sum_cardio_minutes
    ):
        message += f"""    • Total cardio minutes: {history.new_daily_activity_stats.sum_cardio_minutes} {cardio_minutes_icon} {cardio_minutes_record_text}
"""
    if (
        ReportField.peak_minutes in report_settings.fields
        and history.new_daily_activity_stats.sum_peak_minutes
    ):
        message += f"""    • Total peak minutes: {history.new_daily_activity_stats.sum_peak_minutes} {peak_minutes_icon} {peak_minutes_record_text}
"""
    if (
        ReportField.out_of_zone_minutes in report_settings.fields
        and history.new_daily_activity_stats.sum_out_of_zone_minutes
    ):
        message += f"""    • Total out of zone minutes: {history.new_daily_activity_stats.sum_out_of_zone_minutes} {out_of_zone_minutes_icon} {out_of_zone_minutes_record_text}
"""

    return message


@inject
async def create_motivational_message(
    slack_alias: str,
    activity_name: str,
    report_settings: Report,
    history: DailyActivityHistory,
    openai_repository: RemoteOpenAiRepository = Provide[Container.openai_repository],
) -> str:
    """
    Create a motivational message including, if relevant, a note that the goal
        was reached, that a streak has been accomplished, and a motivational
        text created by an AI.

    :return: the motivational message, or an empty string if not relevant.
    """
    motivational_message = ""
    if (
        report_settings.daily_goals
        and report_settings.daily_goals.distance_km
        and history.new_daily_activity_stats.sum_distance_km
        > report_settings.daily_goals.distance_km
    ):
        motivational_message += " Goal reached! 👍"
    if history.streak_distance_km_days:
        motivational_message += f" {history.streak_distance_km_days} day streak! 👏"
        # If we reached our goal streak by a multiple of x days, include
        # an additional motivational message from AI.
        if (
            history.streak_distance_km_days
            % report_settings.ai_motivational_message_frequency_days
            == 0
            and report_settings.daily_goals.distance_km
        ):
            prompt = f"""
Generate a short message, using emojis, of congratulations and encouragement for
<@{slack_alias}> who just finished a {history.streak_distance_km_days} day streak of {activity_name}
doing over {report_settings.daily_goals.distance_km} km every day.
"""
            ai_motivational_message = await openai_repository.create_response(prompt)
            if ai_motivational_message:
                motivational_message += f"""
{ai_motivational_message}"""
    motivational_message += """
"""
    return motivational_message

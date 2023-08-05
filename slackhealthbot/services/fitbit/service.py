import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from slackhealthbot.database import crud
from slackhealthbot.database.models import User
from slackhealthbot.services.fitbit import api
from slackhealthbot.services.models import ActivityData, SleepData
from slackhealthbot.settings import settings


async def save_new_sleep_data(
    db: AsyncSession,
    user: User,
    sleep_data: SleepData,
):
    await crud.update_user(
        db,
        user,
        fitbit_data={
            "last_sleep_start_time": sleep_data.start_time,
            "last_sleep_end_time": sleep_data.end_time,
            "last_sleep_sleep_minutes": sleep_data.sleep_minutes,
            "last_sleep_wake_minutes": sleep_data.wake_minutes,
        },
    )


async def save_new_activity_data(
    db: AsyncSession,
    user: User,
    activity_data: ActivityData,
):
    await crud.upsert_fitbit_activity_data(
        db,
        fitbit_user_id=user.fitbit.id,
        type_id=activity_data.type_id,
        data={
            **activity_data.dict(include={"log_id", "total_minutes", "calories"}),
            **{f"{x.zone}_minutes": x.minutes for x in activity_data.zone_minutes},
        },
    )
    await db.refresh(user)


def _is_new_valid_activity(user: User, activity: ActivityData | None) -> bool:
    return (
        activity
        and activity.type_id in settings.fitbit_activity_type_ids
        and not any(
            x for x in user.fitbit.latest_activities if x.log_id == activity.log_id
        )
    )


async def get_activity(
    db: AsyncSession,
    user: User,
    when: datetime.datetime,
):
    # lazy load activity data
    await user.fitbit.awaitable_attrs.latest_activities
    activity = await api.get_activity(db, user, when)
    if not _is_new_valid_activity(user, activity):
        return None
    await save_new_activity_data(db, user, activity)
    return activity

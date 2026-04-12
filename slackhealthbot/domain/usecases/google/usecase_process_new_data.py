import datetime as dt
import logging
from enum import Enum, auto

from slackhealthbot.core.exceptions import UnknownUserException, UserLoggedOutException
from slackhealthbot.domain.models.users import UserLookup
from slackhealthbot.domain.usecases.fitbit import (
    usecase_post_user_logged_out,
    usecase_process_new_activity,
    usecase_process_new_sleep,
)


class DataType(Enum):
    SLEEP = auto()
    EXERCISE = auto()


async def do(
    data_type: DataType,
    user_lookup: UserLookup,
    dates: set[dt.date],
):
    """
    Process new data for a set of dates.
    """
    try:
        for date in dates:
            if data_type == DataType.SLEEP:
                await usecase_process_new_sleep.do(user_lookup, date)
            else:
                await usecase_process_new_activity.do(user_lookup, date)

    except UserLoggedOutException:
        logging.warning(f"usecase_process_new_data: user logged out {user_lookup}")
        await usecase_post_user_logged_out.do(user_lookup)
    except UnknownUserException:
        logging.warning(f"usecase_process_new_data: unknown user {user_lookup}")

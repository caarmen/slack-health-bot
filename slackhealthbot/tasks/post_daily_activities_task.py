import asyncio
import datetime as dt
import logging
from typing import AsyncContextManager, Callable, Coroutine

from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
)
from slackhealthbot.domain.usecases.fitbit import usecase_process_daily_activities

logger = logging.getLogger(__name__)


async def post_daily_activities(
    local_fitbit_repo_factory: Callable[[], AsyncContextManager[LocalFitbitRepository]],
    activity_type_ids: set[int],
    post_time: dt.time,
) -> Coroutine[None, None, asyncio.Task]:

    async def task():
        while True:
            try:
                logger.info("Processing daily activities")
                now = dt.datetime.now()

                next_task_datetime = now.replace(
                    hour=post_time.hour,
                    minute=post_time.minute,
                    second=post_time.second,
                    microsecond=post_time.microsecond,
                )
                if next_task_datetime < now:
                    next_task_datetime += dt.timedelta(days=1)
                time_until_next_task_datetime_s = (next_task_datetime - now).seconds
                logger.info(
                    f"Sleeping {time_until_next_task_datetime_s} seconds until next daily summary at {next_task_datetime}"
                )
                # Add a few seconds to the sleep duration.
                # This will avoid the following error where our loop was called
                # just before (<500ms before) the scheduled time of 21:00, at 20:59:59,549.
                # We finished the processing quickly (before 20:59:59,778), and
                # scheduled it for the "next 21:00", which was just a few milliseconds in the future.
                # Logs:
                """
    2024-08-18 14:26:08,928 Sleeping 23631 seconds until next daily summary at 2024-08-18 21:00:00

    2024-08-18 21:00:00,195 Sleeping 86399 seconds until next daily summary at 2024-08-19 21:00:00

    2024-08-19 20:59:59,549 Sleeping 0 seconds until next daily summary at 2024-08-19 21:00:00
    2024-08-19 20:59:59,778 Sleeping 0 seconds until next daily summary at 2024-08-19 21:00:00
    2024-08-19 21:00:00,025 Sleeping 86399 seconds until next daily summary at 2024-08-20 21:00:00
                """
                await asyncio.sleep(time_until_next_task_datetime_s + 3)

                async with local_fitbit_repo_factory() as local_fitbit_repo:
                    await usecase_process_daily_activities.do(
                        local_fitbit_repo=local_fitbit_repo,
                        type_ids=activity_type_ids,
                    )
            except Exception:
                logging.error("Error processing daily activities", exc_info=True)

    return asyncio.create_task(task())

import asyncio
import dataclasses
import datetime
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from slackhealthbot.core.exceptions import UserLoggedOutException
from slackhealthbot.data.database.connection import SessionLocal
from slackhealthbot.data.repositories import fitbitrepository
from slackhealthbot.data.repositories.fitbitrepository import UserIdentity
from slackhealthbot.domain.usecases.fitbit import (
    usecase_process_new_activity,
    usecase_process_new_sleep,
)
from slackhealthbot.domain.usecases.slack import usecase_post_user_logged_out
from slackhealthbot.settings import settings


@dataclasses.dataclass
class Cache:
    cache_sleep_success: dict[str, datetime.date] = dataclasses.field(
        default_factory=dict
    )
    cache_fail: dict[str, datetime.date] = dataclasses.field(default_factory=dict)


async def handle_success_poll(
    fitbit_userid: str,
    when: datetime.date,
    cache: Cache,
):
    cache.cache_sleep_success[fitbit_userid] = when
    cache.cache_fail.pop(fitbit_userid, None)


async def handle_fail_poll(
    fitbit_userid: str,
    slack_alias: str,
    when: datetime.date,
    cache: Cache,
):
    last_error_post = cache.cache_fail.get(fitbit_userid)
    if not last_error_post or last_error_post < when:
        usecase_post_user_logged_out.do(
            slack_alias=slack_alias,
            service="fitbit",
        )
        cache.cache_fail[fitbit_userid] = when


async def fitbit_poll(cache: Cache):
    logging.info("fitbit poll")
    today = datetime.date.today()
    try:
        async with SessionLocal() as db:
            await do_poll(db, cache, when=today)
    except Exception:
        logging.error("Error polling fitbit", exc_info=True)
    await schedule_fitbit_poll(cache=cache)


async def do_poll(db: AsyncSession, cache: Cache, when: datetime.date):
    user_identities: list[
        UserIdentity
    ] = await fitbitrepository.get_all_user_identities(db)
    for user_identity in user_identities:
        await fitbit_poll_sleep(
            db,
            cache,
            when,
            fitbit_userid=user_identity.fitbit_userid,
            slack_alias=user_identity.slack_alias,
        )
        await fitbit_poll_activity(
            db,
            cache,
            when,
            fitbit_userid=user_identity.fitbit_userid,
            slack_alias=user_identity.slack_alias,
        )


async def fitbit_poll_activity(
    db: AsyncSession,
    cache: Cache,
    when: datetime.date,
    fitbit_userid: str,
    slack_alias: str,
):
    try:
        await usecase_process_new_activity.do(
            db=db,
            fitbit_userid=fitbit_userid,
            when=datetime.datetime.now(),
        )
    except UserLoggedOutException:
        await handle_fail_poll(
            fitbit_userid=fitbit_userid,
            slack_alias=slack_alias,
            when=when,
            cache=cache,
        )


async def fitbit_poll_sleep(
    db: AsyncSession,
    cache: Cache,
    when: datetime.date,
    fitbit_userid: str,
    slack_alias: str,
):
    latest_successful_poll = cache.cache_sleep_success.get(fitbit_userid)
    if not latest_successful_poll or latest_successful_poll < when:
        try:
            sleep_data = await usecase_process_new_sleep.do(
                db,
                fitbit_userid=fitbit_userid,
                when=when,
            )
        except UserLoggedOutException:
            await handle_fail_poll(
                fitbit_userid=fitbit_userid,
                slack_alias=slack_alias,
                when=when,
                cache=cache,
            )
        else:
            if sleep_data:
                await handle_success_poll(
                    fitbit_userid=fitbit_userid,
                    when=when,
                    cache=cache,
                )


async def schedule_fitbit_poll(
    delay_s: int = settings.fitbit_poll_interval_s, cache: Cache = None
):
    if cache is None:
        cache = Cache()
    loop = asyncio.get_event_loop()
    loop.call_later(float(delay_s), asyncio.create_task, fitbit_poll(cache))
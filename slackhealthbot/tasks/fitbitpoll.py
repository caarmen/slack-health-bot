import asyncio
import dataclasses
import datetime
import logging
from typing import AsyncContextManager, Callable

from dependency_injector.wiring import Provide

from slackhealthbot.containers import Container
from slackhealthbot.core.exceptions import UserLoggedOutException
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
    UserIdentity,
)
from slackhealthbot.domain.remoterepository.remotefitbitrepository import (
    RemoteFitbitRepository,
)
from slackhealthbot.domain.usecases.fitbit import (
    usecase_process_new_activity,
    usecase_process_new_sleep,
)
from slackhealthbot.domain.usecases.slack import usecase_post_user_logged_out
from slackhealthbot.settings import Settings


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
        await usecase_post_user_logged_out.do(
            slack_alias=slack_alias,
            service="fitbit",
        )
        cache.cache_fail[fitbit_userid] = when


async def fitbit_poll(
    cache: Cache,
    local_fitbit_repo: LocalFitbitRepository,
    remote_fitbit_repo: RemoteFitbitRepository,
):
    logging.info("fitbit poll")
    today = datetime.date.today()
    try:
        await do_poll(
            local_fitbit_repo=local_fitbit_repo,
            remote_fitbit_repo=remote_fitbit_repo,
            cache=cache,
            when=today,
        )
    except Exception:
        logging.error("Error polling fitbit", exc_info=True)


async def do_poll(
    local_fitbit_repo: LocalFitbitRepository,
    remote_fitbit_repo: RemoteFitbitRepository,
    cache: Cache,
    when: datetime.date,
):
    user_identities: list[UserIdentity] = (
        await local_fitbit_repo.get_all_user_identities()
    )
    for user_identity in user_identities:
        await fitbit_poll_sleep(
            local_fitbit_repo=local_fitbit_repo,
            remote_fitbit_repo=remote_fitbit_repo,
            cache=cache,
            poll_target=PollTarget(
                when=when,
                user_identity=user_identity,
            ),
        )
        await fitbit_poll_activity(
            local_fitbit_repo=local_fitbit_repo,
            remote_fitbit_repo=remote_fitbit_repo,
            cache=cache,
            poll_target=PollTarget(
                when=when,
                user_identity=user_identity,
            ),
        )


@dataclasses.dataclass
class PollTarget:
    when: datetime.date
    user_identity: UserIdentity


async def fitbit_poll_activity(
    local_fitbit_repo: LocalFitbitRepository,
    remote_fitbit_repo: RemoteFitbitRepository,
    cache: Cache,
    poll_target: PollTarget,
):
    try:
        await usecase_process_new_activity.do(
            local_fitbit_repo=local_fitbit_repo,
            remote_fitbit_repo=remote_fitbit_repo,
            fitbit_userid=poll_target.user_identity.fitbit_userid,
            when=datetime.datetime.now(),
        )
    except UserLoggedOutException:
        await handle_fail_poll(
            fitbit_userid=poll_target.user_identity.fitbit_userid,
            slack_alias=poll_target.user_identity.slack_alias,
            when=poll_target.when,
            cache=cache,
        )


async def fitbit_poll_sleep(
    local_fitbit_repo: LocalFitbitRepository,
    remote_fitbit_repo: RemoteFitbitRepository,
    cache: Cache,
    poll_target: PollTarget,
):
    latest_successful_poll = cache.cache_sleep_success.get(
        poll_target.user_identity.fitbit_userid
    )
    if not latest_successful_poll or latest_successful_poll < poll_target.when:
        try:
            sleep_data = await usecase_process_new_sleep.do(
                local_fitbit_repo=local_fitbit_repo,
                remote_fitbit_repo=remote_fitbit_repo,
                fitbit_userid=poll_target.user_identity.fitbit_userid,
                when=poll_target.when,
            )
        except UserLoggedOutException:
            await handle_fail_poll(
                fitbit_userid=poll_target.user_identity.fitbit_userid,
                slack_alias=poll_target.user_identity.slack_alias,
                when=poll_target.when,
                cache=cache,
            )
        else:
            if sleep_data:
                await handle_success_poll(
                    fitbit_userid=poll_target.user_identity.fitbit_userid,
                    when=poll_target.when,
                    cache=cache,
                )


async def schedule_fitbit_poll(  # noqa: PLR0913 deal with it later
    local_fitbit_repo_factory: Callable[[], AsyncContextManager[LocalFitbitRepository]],
    remote_fitbit_repo: RemoteFitbitRepository,
    initial_delay_s: int | None = None,
    cache: Cache = None,
    settings: Settings = Provide[Container.settings],
):
    if cache is None:
        cache = Cache()

    if initial_delay_s is None:
        initial_delay_s = settings.app_settings.fitbit.poll.interval_seconds

    async def run_with_delay():
        await asyncio.sleep(initial_delay_s)
        while True:
            async with local_fitbit_repo_factory() as local_fitbit_repo:
                await fitbit_poll(
                    cache=cache,
                    local_fitbit_repo=local_fitbit_repo,
                    remote_fitbit_repo=remote_fitbit_repo,
                )
            await asyncio.sleep(settings.app_settings.fitbit.poll.interval_seconds)

    return asyncio.create_task(run_with_delay())

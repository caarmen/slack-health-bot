import random
import string
from asyncio import Task
from contextlib import asynccontextmanager

import uvicorn
from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI, Response
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware

from slackhealthbot import logger
from slackhealthbot.containers import Container
from slackhealthbot.domain.usecases.fitbit.usecase_update_user_oauth import (
    UpdateTokenUseCase as FitbitUpdateTokenUseCase,
)
from slackhealthbot.domain.usecases.withings.usecase_update_user_oauth import (
    UpdateTokenUseCase as WithingsUpdateTokenUseCase,
)
from slackhealthbot.oauth import fitbitconfig as oauth_fitbit
from slackhealthbot.oauth import withingsconfig as oauth_withings
from slackhealthbot.routers.dependencies import (
    fitbit_repository_factory,
    get_remote_fitbit_repository,
    get_remote_withings_repository,
    get_slack_repository,
    request_context_fitbit_repository,
    request_context_withings_repository,
)
from slackhealthbot.routers.fitbit import router as fitbit_router
from slackhealthbot.routers.withings import router as withings_router
from slackhealthbot.settings import settings
from slackhealthbot.tasks import fitbitpoll
from slackhealthbot.tasks.post_daily_activities_task import post_daily_activities


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.configure_logging(settings.app_settings.logging.sql_log_level)
    oauth_withings.configure(
        WithingsUpdateTokenUseCase(
            request_context_withings_repository,
            remote_repo=get_remote_withings_repository(),
        )
    )
    oauth_fitbit.configure(
        FitbitUpdateTokenUseCase(
            request_context_fitbit_repository,
            remote_repo=get_remote_fitbit_repository(),
        )
    )
    schedule_task = None
    if settings.app_settings.fitbit.poll.enabled:
        schedule_task = await fitbitpoll.schedule_fitbit_poll(
            local_fitbit_repo_factory=fitbit_repository_factory(),
            remote_fitbit_repo=get_remote_fitbit_repository(),
            slack_repo=get_slack_repository(),
            initial_delay_s=10,
        )
    daily_activity_task: Task | None = None
    if settings.app_settings.fitbit_daily_activity_type_ids:
        daily_activity_task = await post_daily_activities(
            local_fitbit_repo_factory=fitbit_repository_factory(),
            activity_type_ids=set(settings.app_settings.fitbit_daily_activity_type_ids),
            slack_repo=get_slack_repository(),
            post_time=settings.app_settings.fitbit.activities.daily_report_time,
        )
    yield
    if schedule_task:
        schedule_task.cancel()
    if daily_activity_task:
        daily_activity_task.cancel()


app = FastAPI(
    middleware=[
        Middleware(CorrelationIdMiddleware),
        Middleware(
            SessionMiddleware,
            secret_key="".join(
                random.choice(string.ascii_lowercase) for i in range(32)
            ),
        ),
    ],
    lifespan=lifespan,
)

container = Container()
app.container = container
app.include_router(withings_router)
app.include_router(fitbit_router)


@app.head("/")
def validate_root():
    return Response()


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_config=logger.get_uvicorn_log_config(),
    )

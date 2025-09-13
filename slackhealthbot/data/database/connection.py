import logging
from functools import cache
from pathlib import Path

from dependency_injector.wiring import Provide, inject
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from slackhealthbot.containers import Container
from slackhealthbot.settings import Settings


@inject
def get_connection_url(
    settings: Settings = Provide[Container.settings],
) -> str:
    # In the case of running "alembic upgrade head", it accesses this
    # function without going through the dependency injection.
    if not isinstance(settings, Settings):
        settings = Container.settings.provided()
    return f"sqlite+aiosqlite:///{settings.app_settings.database_path}"


@cache
@inject
def create_async_session_maker(
    settings: Settings = Provide[Container.settings],
) -> async_sessionmaker:
    engine = create_async_engine(
        get_connection_url(),
        connect_args={"check_same_thread": False},
    )
    Path(settings.app_settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    if settings.app_settings.logging.sql_log_level.upper() == "DEBUG":

        def before_cursor_execute(_conn, _cursor, statement, parameters, *args):
            logging.debug(f"{statement}; args={parameters}")

        event.listen(engine.sync_engine, "before_cursor_execute", before_cursor_execute)
    return async_sessionmaker(
        autocommit=False, autoflush=False, bind=engine, future=True
    )

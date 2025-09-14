import logging
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from slackhealthbot.settings import Settings


def get_connection_url(
    settings: Settings | None = None,
) -> str:
    # In the case of running "alembic upgrade head", it accesses this
    # function without going through the dependency injection.
    if not isinstance(settings, Settings):
        # If we put this import at the top of the file, we get a circular dependency issue,
        # as the containers module imports symbols from this file (to build db dependencies).
        from slackhealthbot.containers import Container  # noqa: PLC0415

        settings = Container.settings.provided()
    return f"sqlite+aiosqlite:///{settings.app_settings.database_path}"


def create_async_session_maker(
    settings: Settings,
) -> async_sessionmaker:
    engine = create_async_engine(
        get_connection_url(settings),
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


async def session_context_manager(
    session_factory: async_sessionmaker,
) -> AsyncGenerator[AsyncSession, None]:
    db: AsyncSession = session_factory()
    try:
        yield db
    finally:
        await db.close()

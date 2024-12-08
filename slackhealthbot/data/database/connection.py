import logging
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from slackhealthbot.settings import settings

connection_url = f"sqlite+aiosqlite:///{settings.app_settings.app.database_path}"
Path(settings.app_settings.app.database_path).parent.mkdir(parents=True, exist_ok=True)
engine = create_async_engine(
    connection_url,
    connect_args={"check_same_thread": False},
)
SessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=engine, future=True
)

if settings.app_settings.app.logging.sql_log_level.upper() == "DEBUG":

    def before_cursor_execute(_conn, _cursor, statement, parameters, *args):
        logging.debug(f"{statement}; args={parameters}")

    event.listen(engine.sync_engine, "before_cursor_execute", before_cursor_execute)

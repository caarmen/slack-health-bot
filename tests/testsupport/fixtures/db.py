import logging
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alembic import command
from alembic.config import Config
from slackhealthbot.data.database import connection as db_connection
from slackhealthbot.data.database.models import Base


@pytest.fixture
def sqlalchemy_declarative_base():
    return Base


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "database.db")


@pytest.fixture
def async_connection_url(db_path):
    return f"sqlite+aiosqlite:///{db_path}"


@pytest.fixture
def connection_url(db_path):
    return f"sqlite:///{db_path}"


@pytest.fixture()
def apply_alembic_migration(
    async_connection_url: str,
    monkeypatch: pytest.MonkeyPatch,
):
    with monkeypatch.context() as mp:
        mp.setattr(db_connection, "get_connection_url", lambda: async_connection_url)
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")


@pytest.fixture(autouse=True)
def setup_db(apply_alembic_migration, connection):
    # This fixture ensures that the alembic migration is applied
    # before the connection fixture is used.
    pass


@pytest_asyncio.fixture
async def mocked_async_session(
    mocked_async_session_generator: AsyncGenerator[AsyncSession, None],
) -> AsyncGenerator[AsyncSession, None]:
    async for session in mocked_async_session_generator():
        yield session


@pytest.fixture
def mocked_async_session_generator(async_connection_url: str):
    async def generator() -> AsyncGenerator[AsyncSession, None]:
        engine = create_async_engine(async_connection_url)
        session: AsyncSession = async_sessionmaker(bind=engine)()

        def before_cursor_execute(_conn, _cursor, statement, parameters, *args):
            logging.debug(f"{statement}; args={parameters}")

        event.listen(engine.sync_engine, "before_cursor_execute", before_cursor_execute)
        yield session
        await session.commit()
        await session.close()

    return generator

from pathlib import Path

import pytest
import pytest_asyncio
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
async def mocked_async_session(async_connection_url: str):
    engine = create_async_engine(async_connection_url)
    session: AsyncSession = async_sessionmaker(bind=engine)()
    yield session
    await session.close()

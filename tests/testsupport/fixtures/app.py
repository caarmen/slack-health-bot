from typing import AsyncGenerator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from slackhealthbot.main import app
from slackhealthbot.routers.dependencies import get_db
from slackhealthbot.settings import Settings


@pytest.fixture(autouse=True)
def setup_app_db(
    mocked_async_session_generator: AsyncGenerator[AsyncSession, None],
):
    async def db_override():
        async for session in mocked_async_session_generator():
            yield session

    app.dependency_overrides[get_db] = db_override


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv(
        "SHB_CUSTOM_CONFIG_PATH", "tests/testsupport/config/app-test.yaml"
    )
    return app.container.settings.provided()


@pytest.fixture(autouse=True)
def reset_container():
    # Reset singletons for each test.
    # https://github.com/ets-labs/python-dependency-injector/issues/421
    app.container.reset_singletons()

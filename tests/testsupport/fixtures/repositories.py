import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from slackhealthbot.data.repositories.sqlalchemyfitbitrepository import (
    SQLAlchemyFitbitRepository,
)
from slackhealthbot.data.repositories.sqlalchemywithingsrepository import (
    SQLAlchemyWithingsRepository,
)
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
)
from slackhealthbot.domain.localrepository.localwithingsrepository import (
    LocalWithingsRepository,
)
from slackhealthbot.domain.remoterepository.remotewithingsrepository import (
    RemoteWithingsRepository,
)
from slackhealthbot.remoteservices.repositories.webapiwithingsrepository import (
    WebApiWithingsRepository,
)


@pytest.fixture
def local_withings_repository(
    mocked_async_session: AsyncSession,
) -> LocalWithingsRepository:
    return SQLAlchemyWithingsRepository(db=mocked_async_session)


@pytest.fixture
def remote_withings_repository() -> RemoteWithingsRepository:
    return WebApiWithingsRepository()


@pytest.fixture
def local_fitbit_repository(
    mocked_async_session: AsyncSession,
) -> LocalFitbitRepository:
    return SQLAlchemyFitbitRepository(db=mocked_async_session)

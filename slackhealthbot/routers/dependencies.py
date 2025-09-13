from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import AsyncContextManager, Callable

from fastapi import Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from slackhealthbot.data.database.connection import create_async_session_maker
from slackhealthbot.data.repositories.sqlalchemyfitbitrepository import (
    SQLAlchemyFitbitRepository,
)
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
)

_ctx_db = ContextVar("ctx_db")
_ctx_fitbit_repository = ContextVar("fitbit_repository")


async def get_db():
    db = create_async_session_maker()()
    try:
        # We need to access the db session without having access to
        # fastapi's dependency injection. This happens when our update_token()
        # authlib function is called.
        # Set the db in a ContextVar to allow accessing it outside a fastapi route.
        _ctx_db.set(db)
        yield db
    finally:
        await db.close()
        _ctx_db.set(None)


async def get_local_fitbit_repository(
    db: AsyncSession = Depends(get_db),
) -> LocalFitbitRepository:
    repo = SQLAlchemyFitbitRepository(db=db)
    _ctx_fitbit_repository.set(repo)
    yield repo
    _ctx_fitbit_repository.set(None)


def request_context_fitbit_repository() -> LocalFitbitRepository:
    return _ctx_fitbit_repository.get()


# TODO move this
def fitbit_repository_factory(
    db: AsyncSession | None = None,
) -> Callable[[], AsyncContextManager[LocalFitbitRepository]]:
    @asynccontextmanager
    async def ctx_mgr() -> LocalFitbitRepository:
        autoclose_db = False
        _db = db
        if _db is None:
            _db = create_async_session_maker()()
            autoclose_db = True
        repo = SQLAlchemyFitbitRepository(db=_db)
        _ctx_fitbit_repository.set(repo)
        yield repo
        _ctx_fitbit_repository.set(None)
        if autoclose_db:
            await _db.close()

    return ctx_mgr


templates = Jinja2Templates(directory="templates")

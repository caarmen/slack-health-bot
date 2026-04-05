import datetime as dt
from abc import ABC, abstractmethod

from pydantic import BaseModel

from slackhealthbot.core.models import OAuthFields
from slackhealthbot.domain.models.activity import ActivityData
from slackhealthbot.domain.models.sleep import SleepData


class HealthIds(BaseModel):
    fitbit_user_id: str | None
    health_user_id: str


class RemoteGoogleRepository(ABC):
    @abstractmethod
    def parse_oauth_fields(
        self,
        response_data: dict[str, str],
    ) -> OAuthFields: ...

    @abstractmethod
    async def get_identity(
        self,
        oauth_fields: OAuthFields,
    ) -> HealthIds: ...

    @abstractmethod
    async def get_activities_for_date(
        self,
        oauth_fields: OAuthFields,
        when: dt.date,
    ) -> list[tuple[str, ActivityData]]: ...

    @abstractmethod
    async def get_sleep(
        self,
        oauth_fields: OAuthFields,
        when: dt.date,
    ) -> SleepData | None: ...

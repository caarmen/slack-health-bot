import datetime
from abc import ABC, abstractmethod

from slackhealthbot.core.models import OAuthFields
from slackhealthbot.domain.models.activity import ActivityData
from slackhealthbot.domain.models.sleep import SleepData


class RemoteFitbitRepository(ABC):
    @abstractmethod
    async def subscribe(
        self,
        oauth_fields: OAuthFields,
    ):
        pass

    @abstractmethod
    async def get_activity(
        self, oauth_fields: OAuthFields, when: datetime.datetime
    ) -> tuple[str, ActivityData] | None:
        pass

    @abstractmethod
    async def get_activities_for_date(
        self, oauth_fields: OAuthFields, when: datetime.date
    ) -> list[tuple[str, ActivityData]]:
        pass

    @abstractmethod
    async def get_sleep(
        self,
        oauth_fields: OAuthFields,
        when: datetime.date,
    ) -> SleepData | None:
        pass

    @abstractmethod
    def parse_oauth_fields(
        self,
        response_data: dict[str, str],
    ) -> OAuthFields:
        pass

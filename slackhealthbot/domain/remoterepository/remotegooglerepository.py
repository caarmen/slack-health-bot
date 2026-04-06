from abc import ABC, abstractmethod

from pydantic import BaseModel

from slackhealthbot.core.models import OAuthFields


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

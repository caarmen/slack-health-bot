from abc import ABC, abstractmethod

from slackhealthbot.core.models import OAuthFields


class RemoteGoogleRepository(ABC):
    @abstractmethod
    def parse_oauth_fields(
        self,
        response_data: dict[str, str],
    ) -> OAuthFields: ...

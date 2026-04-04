import datetime

from slackhealthbot.core.models import OAuthFields
from slackhealthbot.domain.remoterepository.remotegooglerepository import (
    RemoteGoogleRepository,
)
from slackhealthbot.settings import Settings


class WebApiGoogleRepository(RemoteGoogleRepository):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

    def parse_oauth_fields(
        self,
        response_data: dict[str, str],
    ) -> OAuthFields:
        return OAuthFields(
            oauth_userid=response_data["userinfo"]["sub"],
            oauth_access_token=response_data["access_token"],
            oauth_refresh_token=response_data["refresh_token"],
            oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(seconds=int(response_data["expires_in"]))
            - datetime.timedelta(minutes=5),
        )

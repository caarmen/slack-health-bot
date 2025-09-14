import datetime

from slackhealthbot.core.models import OAuthFields
from slackhealthbot.domain.remoterepository.remotewithingsrepository import (
    RemoteWithingsRepository,
)
from slackhealthbot.remoteservices.api.withings import subscribeapi, weightapi
from slackhealthbot.settings import Settings


class WebApiWithingsRepository(RemoteWithingsRepository):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

    async def subscribe(
        self,
        oauth_fields: OAuthFields,
    ):
        await subscribeapi.subscribe(oauth_fields, self.settings)

    async def get_last_weight_kg(
        self,
        oauth_fields: OAuthFields,
        startdate: int,
        enddate: int,
    ) -> float | None:
        return await weightapi.get_last_weight_kg(
            oauth_token=oauth_fields,
            startdate=startdate,
            enddate=enddate,
            settings=self.settings,
        )

    def parse_oauth_fields(
        self,
        response_data: dict[str, str],
    ) -> OAuthFields:
        return OAuthFields(
            oauth_userid=response_data["userid"],
            oauth_access_token=response_data["access_token"],
            oauth_refresh_token=response_data["refresh_token"],
            oauth_expiration_date=datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(seconds=int(response_data["expires_in"]))
            - datetime.timedelta(minutes=5),
        )

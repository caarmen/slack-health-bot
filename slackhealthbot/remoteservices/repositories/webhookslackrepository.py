from slackhealthbot.domain.remoterepository.remoteslackrepository import (
    RemoteSlackRepository,
)
from slackhealthbot.remoteservices.api.slack import messageapi
from slackhealthbot.settings import Settings


class WebhookSlackRepository(RemoteSlackRepository):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

    async def post_message(self, message: str):
        await messageapi.post_message(message, self.settings)

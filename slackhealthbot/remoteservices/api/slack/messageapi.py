import httpx

from slackhealthbot.settings import settings


async def post_message(message: str):
    async with httpx.AsyncClient() as client:
        await client.post(
            url=str(settings.secret_settings.slack_webhook_url),
            json={
                "text": message,
            },
            timeout=30.0,
        )

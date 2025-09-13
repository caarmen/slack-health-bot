import httpx

from slackhealthbot.settings import Settings


async def post_message(
    message: str,
    settings: Settings,
):
    async with httpx.AsyncClient(
        timeout=settings.app_settings.request_timeout_s,
        transport=httpx.AsyncHTTPTransport(
            retries=settings.app_settings.request_retries
        ),
    ) as client:
        await client.post(
            url=str(settings.secret_settings.slack_webhook_url),
            json={
                "text": message,
            },
        )

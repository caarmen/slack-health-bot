import datetime as dt
import logging
from asyncio import Lock
from dataclasses import dataclass

import httpx
from dependency_injector.wiring import Provide, inject
from fastapi import Depends

from slackhealthbot.containers import Container
from slackhealthbot.settings import Settings


@dataclass
class LastMessage:
    message: str | None = None
    time_sent: dt.datetime | None = None


last_message = LastMessage()

last_message_lock = Lock()

MESSAGE_DUPLICATION_WINDOW_S = 5


@inject
async def post_message(
    message: str,
    settings: Settings = Depends(Provide[Container.settings]),
):
    # Band-aid quick workaround to avoid sending duplicate messages to Slack.
    # Skip this message if we already sent it "recently".
    now = dt.datetime.now(dt.timezone.utc)
    async with last_message_lock:
        if (
            last_message
            and last_message.message == message
            and (now - last_message.time_sent).seconds < MESSAGE_DUPLICATION_WINDOW_S
        ):
            logging.warning(f"Ignoring duplicate message {last_message}")
            return
        last_message.message = message
        last_message.time_sent = now
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

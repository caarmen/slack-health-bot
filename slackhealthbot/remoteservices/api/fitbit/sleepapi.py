import datetime
import json
import logging
from typing import Annotated, Literal, Self, Union

from dependency_injector.wiring import Provide, inject
from pydantic import BaseModel, Field

from slackhealthbot.containers import Container
from slackhealthbot.core.models import OAuthFields
from slackhealthbot.oauth import requests
from slackhealthbot.settings import Settings


class FitbitSleepItemSummaryItem(BaseModel):
    minutes: int


class FitbitClassicSleepItemSummary(BaseModel):
    awake: FitbitSleepItemSummaryItem
    asleep: FitbitSleepItemSummaryItem


class FitbitStagesSleepItemSummary(BaseModel):
    wake: FitbitSleepItemSummaryItem


class FitbitStagesSleepItemLevels(BaseModel):
    summary: FitbitStagesSleepItemSummary


class FitbitClassicSleepItemLevels(BaseModel):
    summary: FitbitClassicSleepItemSummary


class FitbitSleepItem(BaseModel):
    duration: int
    endTime: str
    isMainSleep: bool
    startTime: str


class FitbitClassicSleepItem(FitbitSleepItem):
    type: Literal["classic"]
    levels: FitbitClassicSleepItemLevels


class FitbitStagesSleepItem(FitbitSleepItem):
    type: Literal["stages"]
    levels: FitbitStagesSleepItemLevels


class FitbitSleep(BaseModel):
    sleep: list[
        Annotated[
            Union[FitbitClassicSleepItem, FitbitStagesSleepItem],
            Field(discriminator="type"),
        ]
    ]

    @classmethod
    def parse(cls, text: bytes | str) -> Self:
        logging.info(f"parse sleep input: {text}")
        return cls(**json.loads(text))


@inject
async def get_sleep(
    oauth_token: OAuthFields,
    when: datetime.date,
    settings: Settings = Provide[Container.settings],
) -> FitbitSleep | None:
    """
    :raises:
        UserLoggedOutException if the refresh token request fails
    """
    logging.info("get_sleep for user")
    when_str = when.strftime("%Y-%m-%d")
    response = await requests.get(
        provider=settings.fitbit_oauth_settings.name,
        token=oauth_token,
        url=f"{settings.fitbit_oauth_settings.base_url}1.2/user/-/sleep/date/{when_str}.json",
    )
    try:
        return FitbitSleep.parse(response.content)
    except Exception as e:
        logging.warning(f"Error parsing sleep: error {e}, input: {input}", exc_info=e)
        return None

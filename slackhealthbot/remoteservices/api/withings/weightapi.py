from typing import Optional

from dependency_injector.wiring import Provide, inject

from slackhealthbot.containers import Container
from slackhealthbot.core.models import OAuthFields
from slackhealthbot.oauth import requests
from slackhealthbot.settings import Settings


@inject
async def get_last_weight_kg(
    oauth_token: OAuthFields,
    startdate: int,
    enddate: int,
    settings: Settings = Provide[Container.settings],
) -> Optional[float]:
    """
    :raises:
        UserLoggedOutException if the refresh token request fails
    """
    # https://developer.withings.com/api-reference/#tag/measure/operation/measure-getmeas
    response = await requests.post(
        provider=settings.withings_oauth_settings.name,
        token=oauth_token,
        url=f"{settings.withings_oauth_settings.base_url}measure",
        data={
            "action": "getmeas",
            "meastype": 1,  # weight
            "category": 1,  # real measures, not objectives
            "startdate": startdate,
            "enddate": enddate,
        },
    )
    response_data = response.json()["body"]
    measuregrps = response_data["measuregrps"]
    if measuregrps:
        last_measuregrp_item = measuregrps[0]
        measures = last_measuregrp_item["measures"]
        if measures:
            last_measure = measures[0]
            weight_kg = last_measure["value"] * pow(10, last_measure["unit"])
            return weight_kg
    return None

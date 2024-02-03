from sqlalchemy.ext.asyncio import AsyncSession

from slackhealthbot.core.models import WeightData
from slackhealthbot.repositories import withingsrepository
from slackhealthbot.services.withings import api


async def do(
    db: AsyncSession,
    withings_userid: str,
    startdate: int,
    enddate: int,
) -> WeightData:
    user: withingsrepository.User = (
        await withingsrepository.get_user_by_withings_userid(
            db,
            withings_userid=withings_userid,
        )
    )
    last_weight_kg = await api.get_last_weight_kg(
        oauth_token=user.oauth_data,
        startdate=startdate,
        enddate=enddate,
    )
    return WeightData(
        weight_kg=last_weight_kg,
        slack_alias=user.identity.slack_alias,
        last_weight_kg=user.fitness_data.last_weight_kg,
    )
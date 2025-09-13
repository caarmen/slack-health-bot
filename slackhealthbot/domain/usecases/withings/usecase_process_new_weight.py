import dataclasses

from slackhealthbot.domain.localrepository.localwithingsrepository import (
    LocalWithingsRepository,
    User,
)
from slackhealthbot.domain.models.weight import WeightData
from slackhealthbot.domain.usecases.slack import usecase_post_weight
from slackhealthbot.domain.usecases.withings import usecase_get_last_weight


@dataclasses.dataclass
class NewWeightParameters:
    withings_userid: str
    startdate: int
    enddate: int


async def do(
    local_withings_repo: LocalWithingsRepository,
    new_weight_parameters: NewWeightParameters,
):
    user: User = await local_withings_repo.get_user_by_withings_userid(
        withings_userid=new_weight_parameters.withings_userid,
    )
    previous_weight_kg: float = user.fitness_data.last_weight_kg

    new_weight_kg: float = await usecase_get_last_weight.do(
        local_repo=local_withings_repo,
        withings_userid=new_weight_parameters.withings_userid,
        startdate=new_weight_parameters.startdate,
        enddate=new_weight_parameters.enddate,
    )
    await local_withings_repo.update_user_weight(
        withings_userid=new_weight_parameters.withings_userid,
        last_weight_kg=new_weight_kg,
    )
    await usecase_post_weight.do(
        weight_data=WeightData(
            weight_kg=new_weight_kg,
            slack_alias=user.identity.slack_alias,
            last_weight_kg=previous_weight_kg,
        ),
    )

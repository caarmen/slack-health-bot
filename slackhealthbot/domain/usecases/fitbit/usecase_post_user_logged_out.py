from slackhealthbot.domain.repository.fitbitrepository import (
    FitbitRepository,
    UserIdentity,
)
from slackhealthbot.domain.usecases.slack import (
    usecase_post_user_logged_out as slack_usecase_post_user_logged_out,
)


async def do(
    repo: FitbitRepository,
    fitbit_userid: str,
):
    user_identity: UserIdentity = await repo.get_user_identity_by_fitbit_userid(
        fitbit_userid=fitbit_userid,
    )
    await slack_usecase_post_user_logged_out.do(
        slack_alias=user_identity.slack_alias,
        service="fitbit",
    )

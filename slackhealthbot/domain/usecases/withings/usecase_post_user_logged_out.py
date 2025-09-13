from dependency_injector.wiring import Provide, inject

from slackhealthbot.containers import Container
from slackhealthbot.domain.localrepository.localwithingsrepository import (
    LocalWithingsRepository,
    UserIdentity,
)
from slackhealthbot.domain.usecases.slack import (
    usecase_post_user_logged_out as slack_usecase_post_user_logged_out,
)


@inject
async def do(
    withings_userid: str,
    withings_repo: LocalWithingsRepository = Provide[
        Container.local_withings_repository
    ],
):
    user_identity: UserIdentity = (
        await withings_repo.get_user_identity_by_withings_userid(
            withings_userid=withings_userid,
        )
    )
    await slack_usecase_post_user_logged_out.do(
        slack_alias=user_identity.slack_alias,
        service="withings",
    )

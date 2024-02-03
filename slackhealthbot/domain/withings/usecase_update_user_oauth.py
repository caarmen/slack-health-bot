from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from slackhealthbot.core.models import OAuthFields
from slackhealthbot.database.connection import ctx_db
from slackhealthbot.domain.oauth import usecase_parse_oauth
from slackhealthbot.repositories import withingsrepository


async def do(
    token: dict[str, Any],
    **_kwargs,
):
    db: AsyncSession = ctx_db.get()
    oauth_fields: OAuthFields = usecase_parse_oauth.do(token)
    await withingsrepository.update_oauth_data(
        db,
        withings_userid=oauth_fields.oauth_userid,
        oauth_data=withingsrepository.OAuthData(
            oauth_access_token=oauth_fields.oauth_access_token,
            oauth_refresh_token=oauth_fields.oauth_refresh_token,
            oauth_expiration_date=oauth_fields.oauth_expiration_date,
        ),
    )
    return await withingsrepository.get_user_by_withings_userid(
        db,
        withings_userid=oauth_fields.oauth_userid,
    )
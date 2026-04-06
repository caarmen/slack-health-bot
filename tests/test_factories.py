from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from slackhealthbot.data.database.models import (
    FitbitActivity,
    FitbitUser,
    User,
    WithingsUser,
)
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
)
from slackhealthbot.domain.localrepository.localwithingsrepository import (
    LocalWithingsRepository,
)
from slackhealthbot.domain.models.activity import (
    ActivityData,
    ActivityZone,
    ActivityZoneMinutes,
)
from slackhealthbot.domain.models.users import FitbitUserLookup
from tests.testsupport.factories.factories import (
    FitbitActivityFactory,
    FitbitUserFactory,
    UserFactory,
    WithingsUserFactory,
)


@pytest.mark.asyncio
async def test_user_factory(
    user_factory: UserFactory,
    mocked_async_session,
):
    user: User = user_factory.create()
    assert isinstance(user.slack_alias, str)
    assert isinstance(user.id, int)
    assert isinstance(user.withings, WithingsUser)
    assert isinstance(user.fitbit, FitbitUser)
    db_user: User = (
        await mocked_async_session.scalars(
            statement=select(User).where(User.slack_alias == user.slack_alias)
        )
    ).one()
    assert user.id == db_user.id
    assert user.slack_alias == db_user.slack_alias
    assert user.withings.id == db_user.withings.id
    assert user.fitbit.id == db_user.fitbit.id


@pytest.mark.asyncio
async def test_withings_user_factory(
    user_factory: UserFactory,
    withings_user_factory: WithingsUserFactory,
    local_withings_repository: LocalWithingsRepository,
):
    user: User = user_factory.create(withings=None)
    withings_user: WithingsUser = withings_user_factory.create(user_id=user.id)
    assert isinstance(withings_user.oauth_access_token, str)
    assert isinstance(withings_user.oauth_refresh_token, str)
    assert isinstance(withings_user.oauth_userid, str)
    assert isinstance(withings_user.oauth_expiration_date, datetime)
    assert isinstance(withings_user.last_weight, float)
    assert isinstance(user, User)

    repo_user = await local_withings_repository.get_user_by_withings_userid(
        withings_userid=withings_user.oauth_userid
    )
    assert repo_user.identity.withings_userid == withings_user.oauth_userid
    assert repo_user.oauth_data.oauth_access_token == withings_user.oauth_access_token
    assert repo_user.oauth_data.oauth_refresh_token == withings_user.oauth_refresh_token
    assert (
        repo_user.oauth_data.oauth_expiration_date
        == withings_user.oauth_expiration_date.replace(tzinfo=timezone.utc)
    )
    assert repo_user.fitness_data.last_weight_kg == withings_user.last_weight


@pytest.mark.asyncio
async def test_fitbit_user_factory(
    user_factory: UserFactory,
    fitbit_user_factory: FitbitUserFactory,
    local_fitbit_repository: LocalFitbitRepository,
):
    user: User = user_factory.create(fitbit=None)
    fitbit_user: FitbitUser = fitbit_user_factory.create(user_id=user.id)
    assert isinstance(fitbit_user.oauth_access_token, str)
    assert isinstance(fitbit_user.oauth_refresh_token, str)
    assert isinstance(fitbit_user.oauth_userid, str)
    assert isinstance(fitbit_user.oauth_expiration_date, datetime)
    assert isinstance(user, User)

    repo_user = await local_fitbit_repository.get_user_by_lookup(
        FitbitUserLookup(user_id=fitbit_user.oauth_userid)
    )
    assert repo_user.oauth_data.oauth_access_token == fitbit_user.oauth_access_token
    assert repo_user.oauth_data.oauth_refresh_token == fitbit_user.oauth_refresh_token
    assert repo_user.identity.fitbit_userid == fitbit_user.oauth_userid
    assert (
        repo_user.oauth_data.oauth_expiration_date
        == fitbit_user.oauth_expiration_date.replace(tzinfo=timezone.utc)
    )


@pytest.mark.asyncio
async def test_fitbit_activity_factory(
    user_factory: UserFactory,
    fitbit_user_factory: FitbitUserFactory,
    fitbit_activity_factory: FitbitActivityFactory,
    local_fitbit_repository: LocalFitbitRepository,
):
    user: User = user_factory.create(fitbit=None)
    fitbit_user: FitbitUser = fitbit_user_factory.create(user_id=user.id)
    fitbit_activity: FitbitActivity = fitbit_activity_factory.create(
        fitbit_user_id=fitbit_user.id
    )
    repo_activity: ActivityData = (
        await local_fitbit_repository.get_latest_activity_by_user_and_type(
            user_lookup=fitbit_user.lookup,
            type_id=fitbit_activity.type_id,
        )
    )
    assert repo_activity.log_id == fitbit_activity.log_id
    assert repo_activity.type_id == fitbit_activity.type_id
    assert repo_activity.total_minutes == fitbit_activity.total_minutes
    assert repo_activity.calories == fitbit_activity.calories
    assert repo_activity.distance_km == fitbit_activity.distance_km
    assert repo_activity.zone_minutes == [
        ActivityZoneMinutes(
            zone=ActivityZone.PEAK,
            minutes=fitbit_activity.peak_minutes,
        ),
        ActivityZoneMinutes(
            zone=ActivityZone.CARDIO,
            minutes=fitbit_activity.cardio_minutes,
        ),
        ActivityZoneMinutes(
            zone=ActivityZone.FAT_BURN,
            minutes=fitbit_activity.fat_burn_minutes,
        ),
        ActivityZoneMinutes(
            zone=ActivityZone.OUT_OF_ZONE,
            minutes=fitbit_activity.out_of_zone_minutes,
        ),
    ]

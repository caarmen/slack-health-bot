import datetime

from sqlalchemy import and_, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from slackhealthbot.core.exceptions import UnknownUserException
from slackhealthbot.core.models import OAuthFields
from slackhealthbot.data.database import models
from slackhealthbot.domain.localrepository.localfitbitrepository import (
    LocalFitbitRepository,
    User,
    UserIdentity,
)
from slackhealthbot.domain.models.activity import (
    ActivityData,
    ActivityZone,
    ActivityZoneMinutes,
    DailyActivityStats,
    TopActivityStats,
    TopDailyActivityStats,
)
from slackhealthbot.domain.models.sleep import SleepData


class SQLAlchemyFitbitRepository(LocalFitbitRepository):

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(
        self,
        slack_alias: str,
        fitbit_userid: str,
        oauth_data: OAuthFields,
    ) -> User:
        user = (
            await self.db.scalars(
                statement=select(models.User).where(
                    models.User.slack_alias == slack_alias
                )
            )
        ).one_or_none()
        if not user:
            user = models.User(slack_alias=slack_alias)
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)

        fitbit_user = models.FitbitUser(
            user_id=user.id,
            oauth_userid=fitbit_userid,
            oauth_access_token=oauth_data.oauth_access_token,
            oauth_refresh_token=oauth_data.oauth_refresh_token,
            oauth_expiration_date=oauth_data.oauth_expiration_date,
        )
        self.db.add(fitbit_user)
        await self.db.commit()
        await self.db.refresh(fitbit_user)

        return User(
            identity=UserIdentity(
                fitbit_userid=fitbit_user.oauth_userid,
                slack_alias=slack_alias,
            ),
            oauth_data=OAuthFields(
                oauth_userid=fitbit_userid,
                oauth_access_token=fitbit_user.oauth_access_token,
                oauth_refresh_token=fitbit_user.oauth_refresh_token,
                oauth_expiration_date=fitbit_user.oauth_expiration_date.replace(
                    tzinfo=datetime.timezone.utc
                ),
            ),
        )

    async def get_user_identity_by_fitbit_userid(
        self,
        fitbit_userid: str,
    ) -> UserIdentity | None:
        user: models.User = (
            await self.db.scalars(
                statement=select(models.User)
                .join(models.User.fitbit)
                .where(models.FitbitUser.oauth_userid == fitbit_userid)
            )
        ).one_or_none()
        return (
            UserIdentity(
                fitbit_userid=user.fitbit.oauth_userid,
                slack_alias=user.slack_alias,
            )
            if user
            else None
        )

    async def get_all_user_identities(
        self,
    ) -> list[UserIdentity]:
        users = await self.db.scalars(
            statement=select(models.User).join(models.User.fitbit)
        )
        return [
            UserIdentity(fitbit_userid=x.fitbit.oauth_userid, slack_alias=x.slack_alias)
            for x in users
        ]

    async def get_oauth_data_by_fitbit_userid(
        self,
        fitbit_userid: str,
    ) -> OAuthFields:
        fitbit_user: models.FitbitUser = (
            await self.db.scalars(
                statement=select(models.FitbitUser).where(
                    models.FitbitUser.oauth_userid == fitbit_userid
                )
            )
        ).one()
        return OAuthFields(
            oauth_userid=fitbit_user.oauth_userid,
            oauth_access_token=fitbit_user.oauth_access_token,
            oauth_refresh_token=fitbit_user.oauth_refresh_token,
            oauth_expiration_date=fitbit_user.oauth_expiration_date.replace(
                tzinfo=datetime.timezone.utc
            ),
        )

    async def get_user_by_fitbit_userid(
        self,
        fitbit_userid: str,
    ) -> User:
        user: models.User = (
            await self.db.scalars(
                statement=select(models.User)
                .join(models.User.fitbit)
                .where(models.FitbitUser.oauth_userid == fitbit_userid)
            )
        ).one_or_none()
        if not user:
            raise UnknownUserException
        return User(
            identity=UserIdentity(
                fitbit_userid=user.fitbit.oauth_userid,
                slack_alias=user.slack_alias,
            ),
            oauth_data=OAuthFields(
                oauth_userid=fitbit_userid,
                oauth_access_token=user.fitbit.oauth_access_token,
                oauth_refresh_token=user.fitbit.oauth_refresh_token,
                oauth_expiration_date=user.fitbit.oauth_expiration_date.replace(
                    tzinfo=datetime.timezone.utc
                ),
            ),
        )

    async def get_latest_activity_by_user_and_type(
        self,
        fitbit_userid: str,
        type_id: int,
    ) -> ActivityData | None:
        db_activity: models.FitbitActivity = await self.db.scalar(
            statement=select(models.FitbitActivity)
            .join(
                models.FitbitUser,
                models.FitbitUser.id == models.FitbitActivity.fitbit_user_id,
            )
            .where(
                and_(
                    models.FitbitUser.oauth_userid == fitbit_userid,
                    models.FitbitActivity.type_id == type_id,
                )
            )
            .order_by(desc(models.FitbitActivity.updated_at))
            .limit(1)
        )
        return _db_activity_to_domain_activity(db_activity) if db_activity else None

    async def get_activity_by_user_and_log_id(
        self,
        fitbit_userid: str,
        log_id: int,
    ) -> ActivityData | None:
        db_activity: models.FitbitActivity = (
            await self.db.scalars(
                statement=select(models.FitbitActivity)
                .join(models.FitbitUser)
                .where(
                    and_(
                        models.FitbitUser.oauth_userid == fitbit_userid,
                        models.FitbitActivity.log_id == log_id,
                    )
                )
            )
        ).one_or_none()
        return _db_activity_to_domain_activity(db_activity) if db_activity else None

    async def create_activity_for_user(
        self,
        fitbit_userid: str,
        activity: ActivityData,
    ):
        user: models.FitbitUser = (
            await self.db.scalars(
                statement=select(models.FitbitUser).where(
                    models.FitbitUser.oauth_userid == fitbit_userid
                )
            )
        ).one_or_none()
        fitbit_activity = models.FitbitActivity(
            log_id=activity.log_id,
            type_id=activity.type_id,
            total_minutes=activity.total_minutes,
            calories=activity.calories,
            distance_km=activity.distance_km,
            **{f"{x.zone}_minutes": x.minutes for x in activity.zone_minutes},
            fitbit_user_id=user.id,
        )
        self.db.add(fitbit_activity)
        await self.db.commit()

    async def update_sleep_for_user(
        self,
        fitbit_userid: str,
        sleep: SleepData,
    ):
        await self.db.execute(
            statement=update(models.FitbitUser)
            .where(models.FitbitUser.oauth_userid == fitbit_userid)
            .values(
                last_sleep_start_time=sleep.start_time,
                last_sleep_end_time=sleep.end_time,
                last_sleep_sleep_minutes=sleep.sleep_minutes,
                last_sleep_wake_minutes=sleep.wake_minutes,
            )
        )

    async def get_sleep_by_fitbit_userid(
        self,
        fitbit_userid: str,
    ) -> SleepData | None:
        fitbit_user: models.FitbitUser = (
            await self.db.scalars(
                statement=select(models.FitbitUser).where(
                    models.FitbitUser.oauth_userid == fitbit_userid
                )
            )
        ).one_or_none()
        if not fitbit_user:
            raise UnknownUserException
        if not fitbit_user or not fitbit_user.last_sleep_end_time:
            return None
        return SleepData(
            start_time=fitbit_user.last_sleep_start_time,
            end_time=fitbit_user.last_sleep_end_time,
            sleep_minutes=fitbit_user.last_sleep_sleep_minutes,
            wake_minutes=fitbit_user.last_sleep_wake_minutes,
        )

    async def update_oauth_data(
        self,
        fitbit_userid: str,
        oauth_data: OAuthFields,
    ):
        await self.db.execute(
            statement=update(models.FitbitUser)
            .where(models.FitbitUser.oauth_userid == fitbit_userid)
            .values(
                oauth_access_token=oauth_data.oauth_access_token,
                oauth_refresh_token=oauth_data.oauth_refresh_token,
                oauth_expiration_date=oauth_data.oauth_expiration_date,
            )
        )
        await self.db.commit()

    async def get_top_activity_stats_by_user_and_activity_type(
        self,
        fitbit_userid: str,
        type_id: int,
        since: datetime.datetime | None = None,
    ) -> TopActivityStats:

        columns = [
            models.FitbitActivity.calories,
            models.FitbitActivity.distance_km,
            models.FitbitActivity.total_minutes,
            models.FitbitActivity.fat_burn_minutes,
            models.FitbitActivity.cardio_minutes,
            models.FitbitActivity.peak_minutes,
        ]
        conditions = [
            models.FitbitUser.oauth_userid == fitbit_userid,
            models.FitbitActivity.type_id == type_id,
        ]
        if since:
            conditions.append(models.FitbitActivity.updated_at >= since)

        subqueries = [
            select(func.max(column))
            .join(models.FitbitUser)
            .where(and_(*conditions))
            .label(f"top_{column.name}")
            for column in columns
        ]
        results = await self.db.execute(statement=select(*subqueries))
        # noinspection PyProtectedMember
        row = results.one()._asdict()

        return TopActivityStats(
            top_calories=row["top_calories"],
            top_distance_km=row["top_distance_km"],
            top_total_minutes=row["top_total_minutes"],
            top_zone_minutes=[
                ActivityZoneMinutes(
                    zone=ActivityZone[x.upper()],
                    minutes=row.get(f"top_{x}_minutes"),
                )
                for x in ActivityZone
                if row.get(f"top_{x}_minutes")
            ],
        )

    async def get_latest_daily_activity_by_user_and_activity_type(
        self,
        fitbit_userid: str,
        type_id: int,
        before: datetime.date | None = None,
    ) -> DailyActivityStats | None:
        activity_date = before if before else datetime.date.today()
        daily_activity: models.FitbitDailyActivity = (
            await self.db.scalars(
                statement=select(models.FitbitDailyActivity)
                .join(models.FitbitUser)
                .join(models.User)
                .where(
                    and_(
                        models.FitbitDailyActivity.date < activity_date,
                        models.FitbitUser.oauth_userid == fitbit_userid,
                        models.FitbitDailyActivity.type_id == type_id,
                    )
                )
                .order_by(desc(models.FitbitDailyActivity.date))
            )
        ).first()
        if not daily_activity:
            return None
        return DailyActivityStats(
            date=daily_activity.date,
            fitbit_userid=daily_activity.fitbit_user.oauth_userid,
            slack_alias=daily_activity.fitbit_user.user.slack_alias,
            type_id=daily_activity.type_id,
            count_activities=daily_activity.count_activities,
            sum_calories=daily_activity.sum_calories,
            sum_distance_km=daily_activity.sum_distance_km,
            sum_total_minutes=daily_activity.sum_total_minutes,
            sum_fat_burn_minutes=daily_activity.sum_fat_burn_minutes,
            sum_cardio_minutes=daily_activity.sum_cardio_minutes,
            sum_peak_minutes=daily_activity.sum_peak_minutes,
            sum_out_of_zone_minutes=daily_activity.sum_out_of_zone_minutes,
        )

    async def get_daily_activity_streak_days_count_for_user_and_activity_type(
        self,
        fitbit_userid: str,
        type_id: int,
        *,
        before: datetime.date | None = None,
        min_distance_km: float | None = None,
    ) -> int:
        activity_date = before if before else datetime.date.today()
        before_date_daily_activity: models.FitbitDailyActivity = (
            await self.db.scalars(
                statement=select(models.FitbitDailyActivity)
                .join(models.FitbitUser)
                .join(models.User)
                .where(
                    and_(
                        models.FitbitDailyActivity.date == activity_date,
                        models.FitbitUser.oauth_userid == fitbit_userid,
                        models.FitbitDailyActivity.type_id == type_id,
                    )
                )
                .order_by(desc(models.FitbitDailyActivity.date))
            )
        ).first()

        # If the goal wasn't met today, we're not in a streak. Return 0.
        if not before_date_daily_activity or (
            min_distance_km is not None
            and before_date_daily_activity.sum_distance_km < min_distance_km
        ):
            return 0

        today_filters = []
        yesterday_filters = []
        yesterday_activity_alias = aliased(models.FitbitDailyActivity)
        if min_distance_km is not None:
            today_filters.append(
                models.FitbitDailyActivity.sum_distance_km >= min_distance_km
            )
            yesterday_filters.append(
                yesterday_activity_alias.sum_distance_km >= min_distance_km
            )
        # The idea of this SQL query:
        # Example:
        # Our goal is 20km.
        # We've logged the following activities, descending cronological order:
        #
        # Friday: 25km
        # Thursday: 22km
        # Wednesday: no activity
        # Tuesday: 21km
        # Monday: 15km
        # Sunday: no activity
        # Saturday: 23km

        # Start with a query on the relevant daily activities.
        #  ("Relevant" means for the given user and activity type, and optionally
        #  with the given minimum distance_km.)
        #
        # Join (outer) on the daily activities table as "yesterday" matching the same "relevant" criteria,
        # and also with a filter comparing the dates: the initial daily activities
        # date is one day in the future compared to "yesterday's" daily activities.
        #
        # If, on a given day, there was no relevant activity on the previous day, the "yesterday" fields
        # in the result will be null.
        #
        # We add, in the WHERE clause, a condition to look for this "null yesterday".
        #
        # The query will thus only return rows for daily activities where there was no daily activity
        # the previous day.
        #
        # We get the most recent of these rows.
        #
        # This is the beginning of our streak!
        statement = (
            select(models.FitbitDailyActivity)
            .join(models.FitbitUser)
            # Supposing we're currently Friday.
            #
            # At this point, we have rows for (descending cronological order):
            #   Friday: 25km   <--- met goal, in current streak
            #   Thursday: 22km <--- met goal, in current streak
            #   Tuesday: 21km  <--- met goal
            #   Monday: 15km   <--- didn't meet goal
            #   Saturday: 23km <--- met goal
            .outerjoin(
                yesterday_activity_alias,
                and_(
                    models.FitbitDailyActivity.type_id
                    == yesterday_activity_alias.type_id,
                    models.FitbitDailyActivity.fitbit_user_id
                    == yesterday_activity_alias.fitbit_user_id,
                    models.FitbitDailyActivity.date
                    == func.date(yesterday_activity_alias.date, "+1 days"),
                    *yesterday_filters,
                ),
            )
            # At this point, we have rows for (descending cronological order):
            #   "Today"             "Yesterday"
            #   -----------------   ---------------------------------------
            #   Friday: 25km        Thursday: 22km
            #   Thursday: 22km      (null - no activity on Wednesday)
            #   Tuesday: 21km       (null - Monday wasn't at least 20km)
            #   Monday: 15km        (null - no activity on Sunday)
            #   Saturday: 23km      (null - no activity before)
            .where(
                and_(
                    models.FitbitDailyActivity.date <= activity_date,
                    models.FitbitUser.oauth_userid == fitbit_userid,
                    models.FitbitDailyActivity.type_id == type_id,
                    yesterday_activity_alias.date
                    == None,  # noqa E711 (sqlalchemy needs this)
                    *today_filters,
                )
                # At this point, we eliminate some rows:
                #   Friday: it has a non-null value for "Yesterday"
                #   Monday: was < 20km.
                #
                # We now have rows for (descending cronological order):
                #   "Today"             "Yesterday"
                #   -----------------   ---------------------------------------
                #   Thursday: 22km      (null - no activity on Wednesday)
                #   Tuesday: 21km       (null - Monday wasn't at least 20km)
                #   Saturday: 23km      (null - no activity before)
            )
            .order_by(desc(models.FitbitDailyActivity.date))
        )
        daily_activity: models.FitbitDailyActivity = (
            await self.db.scalars(statement=statement)
        ).first()
        # We now take the first row:
        #   "Today"             "Yesterday"
        #   -----------------   ---------------------------------------
        #   Thursday: 22km      (null - no activity on Wednesday)
        #
        # The first day in our streak is Thursday.
        if not daily_activity:
            return 0
        return (activity_date - daily_activity.date).days + 1

    async def get_daily_activities_by_type(
        self,
        type_ids: set[int],
        when: datetime.date | None = None,
    ) -> list[DailyActivityStats]:
        activity_date = when if when else datetime.date.today()
        daily_activities: list[models.FitbitDailyActivity] = await self.db.scalars(
            statement=select(models.FitbitDailyActivity)
            .join(models.FitbitUser)
            .join(models.User)
            .where(
                and_(
                    models.FitbitDailyActivity.date == activity_date,
                    models.FitbitDailyActivity.type_id.in_(type_ids),
                )
            )
        )
        return [
            DailyActivityStats(
                date=daily_activity.date,
                fitbit_userid=daily_activity.fitbit_user.oauth_userid,
                slack_alias=daily_activity.fitbit_user.user.slack_alias,
                type_id=daily_activity.type_id,
                count_activities=daily_activity.count_activities,
                sum_calories=daily_activity.sum_calories,
                sum_distance_km=daily_activity.sum_distance_km,
                sum_total_minutes=daily_activity.sum_total_minutes,
                sum_fat_burn_minutes=daily_activity.sum_fat_burn_minutes,
                sum_cardio_minutes=daily_activity.sum_cardio_minutes,
                sum_peak_minutes=daily_activity.sum_peak_minutes,
                sum_out_of_zone_minutes=daily_activity.sum_out_of_zone_minutes,
            )
            for daily_activity in daily_activities
        ]

    async def get_top_daily_activity_stats_by_user_and_activity_type(
        self,
        fitbit_userid: str,
        type_id: int,
        since: datetime.datetime | None = None,
    ) -> TopActivityStats:
        columns = [
            models.FitbitDailyActivity.count_activities,
            models.FitbitDailyActivity.sum_calories,
            models.FitbitDailyActivity.sum_distance_km,
            models.FitbitDailyActivity.sum_total_minutes,
            models.FitbitDailyActivity.sum_fat_burn_minutes,
            models.FitbitDailyActivity.sum_cardio_minutes,
            models.FitbitDailyActivity.sum_peak_minutes,
            models.FitbitDailyActivity.sum_out_of_zone_minutes,
        ]
        conditions = [
            models.FitbitUser.oauth_userid == fitbit_userid,
            models.FitbitDailyActivity.type_id == type_id,
        ]
        if since:
            conditions.append(models.FitbitDailyActivity.date >= since)

        subqueries = [
            select(func.max(column))
            .join(models.FitbitUser)
            .where(and_(*conditions))
            .label(f"top_{column.name}")
            for column in columns
        ]

        results = await self.db.execute(statement=select(*subqueries))

        # noinspection PyProtectedMember
        row = results.one()._asdict()
        return TopDailyActivityStats(**row)


def _db_activity_to_domain_activity(
    db_activity: models.FitbitActivity,
) -> ActivityData:
    return ActivityData(
        log_id=db_activity.log_id,
        type_id=db_activity.type_id,
        calories=db_activity.calories,
        distance_km=db_activity.distance_km,
        total_minutes=db_activity.total_minutes,
        zone_minutes=[
            ActivityZoneMinutes(
                zone=ActivityZone[x.upper()],
                minutes=getattr(db_activity, f"{x}_minutes"),
            )
            for x in ActivityZone
            if getattr(db_activity, f"{x}_minutes")
        ],
    )

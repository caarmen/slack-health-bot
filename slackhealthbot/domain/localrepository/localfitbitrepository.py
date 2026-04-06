import dataclasses
import datetime
from abc import ABC, abstractmethod

from slackhealthbot.core.models import OAuthFields
from slackhealthbot.domain.models.activity import (
    ActivityData,
    DailyActivityStats,
    TopActivityStats,
)
from slackhealthbot.domain.models.sleep import SleepData
from slackhealthbot.domain.models.users import (
    FitbitUserLookup,
    HealthUserLookup,
    UserLookup,
)


@dataclasses.dataclass
class UserIdentity:
    fitbit_userid: str | None
    health_user_id: str | None
    slack_alias: str

    @property
    def user_lookup(self) -> UserLookup:
        if self.health_user_id:
            return HealthUserLookup(user_id=self.health_user_id)
        return FitbitUserLookup(user_id=self.fitbit_userid)


@dataclasses.dataclass
class User:
    identity: UserIdentity
    oauth_data: OAuthFields


class LocalFitbitRepository(ABC):
    @abstractmethod
    async def create_user(
        self,
        slack_alias: str,
        fitbit_user_id: str | None,
        health_user_id: str | None,
        oauth_data: OAuthFields,
    ) -> User:
        pass

    @abstractmethod
    async def get_user_identity(
        self,
        user_lookup: UserLookup,
    ) -> UserIdentity | None: ...

    @abstractmethod
    async def get_all_user_identities(self) -> list[UserIdentity]:
        pass

    @abstractmethod
    async def get_oauth_data_by_user_lookup(
        self,
        user_lookup: UserLookup,
    ) -> OAuthFields:
        pass

    @abstractmethod
    async def get_user_by_lookup(
        self,
        user_lookup: UserLookup,
    ) -> User: ...

    @abstractmethod
    async def get_latest_activity_by_user_and_type(
        self,
        user_lookup: UserLookup,
        type_id: int,
    ) -> ActivityData | None:
        pass

    @abstractmethod
    async def get_activity_by_user_and_log_id(
        self,
        user_lookup: UserLookup,
        log_id: str,
    ) -> ActivityData | None:
        pass

    @abstractmethod
    async def upsert_activity_for_user(
        self,
        user_lookup: UserLookup,
        activity: ActivityData,
    ) -> bool:
        """
        :return: True if a new activity was created, False if an existing activity was updated.
        """
        pass

    @abstractmethod
    async def update_sleep_for_user(
        self,
        user_lookup: UserLookup,
        sleep: SleepData,
    ):
        pass

    async def get_sleep_by_user_lookup(
        self,
        user_lookup: UserLookup,
    ) -> SleepData | None: ...

    @abstractmethod
    async def update_oauth_data(
        self,
        oauth_userid: str,
        oauth_data: OAuthFields,
    ):
        pass

    @abstractmethod
    async def update_oauth_data_by_fitbit_user_id(
        self,
        fitbit_user_id: str,
        oauth_data: OAuthFields,
    ): ...

    @abstractmethod
    async def update_user_ids(
        self, oauth_userid: str, fitbit_user_id: str | None, health_user_id: str | None
    ): ...

    @abstractmethod
    async def update_token_by_refresh_token(
        self,
        refresh_token: str,
        new_access_token: str,
        new_expiration_date: datetime.datetime,
    ): ...

    @abstractmethod
    async def get_top_activity_stats_by_user_and_activity_type(
        self,
        user_lookup: UserLookup,
        type_id: int,
        since: datetime.datetime | None = None,
    ) -> TopActivityStats:
        pass

    @abstractmethod
    async def get_latest_daily_activity_by_user_and_activity_type(
        self,
        user_lookup: UserLookup,
        primary_type_id: int,
        secondary_type_id: int | None = None,
        before: datetime.date | None = None,
    ) -> DailyActivityStats | None:
        """
        Get the latest daily stats for the given user and activity type, before the given date..
        If no date is provided, today's date is used.
        """
        pass

    @abstractmethod
    async def get_daily_activity_streak_days_count_for_user_and_activity_type(  # noqa: PLR0913
        self,
        user_lookup: UserLookup,
        primary_type_id: int,
        *,
        secondary_type_id: int | None = None,
        before: datetime.date | None = None,
        min_distance_km: float | None = None,
        days_without_activies_break_streak=True,
    ) -> int:
        """
        The streak is the number of days, up until and including the given "before" date
        for which activity meeting a critera was logged.

        Currently the only supported criteria is min_distance_km.

        If before is not provided, before is set to the current date.

        If min_distance_km is provided, only days where the logged distance is at least
        this value count toward the streak.

        :param days_without_activities_break_streak: If True, then days without the given
            type of activity logged for the user will break the streak.

            If False, then these days don't count toward the number of days in the streak
            count, but they don't break the streak. Only days with activity logs but not
            matching the criteria will break the streak.

        :return: 0 if no activity is logged for the "before" date, or if activity was logged
            for the "before" date but does not meet the given min_distance_km.

        :return: the number of days in the streak otherwise.
        """
        pass

    @abstractmethod
    async def get_daily_activities_by_type(
        self,
        type_ids: set[int],
        when: datetime.date | None = None,
    ) -> list[DailyActivityStats]:
        """
        Get the stats for the given date and activity types.
        If no date is provided, returns the stats for today.
        """
        pass

    @abstractmethod
    async def get_top_daily_activity_stats_by_user_and_activity_type(
        self,
        user_lookup: UserLookup,
        type_id: int,
        since: datetime.datetime | None = None,
    ) -> TopActivityStats:
        """
        Get the top daily activity stats for the given user and activity type.
        """
        pass

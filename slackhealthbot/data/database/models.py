from datetime import date as dt_date
from datetime import datetime
from typing import Optional

from sqlalchemy import Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship

from slackhealthbot.domain.models.users import (
    FitbitUserLookup,
    HealthUserLookup,
    UserLookup,
)

Base = declarative_base()


class TimestampMixin(Base):
    __abstract__ = True
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        onupdate=func.now(), server_default=func.now()
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    slack_alias: Mapped[str] = mapped_column(unique=True, index=True)
    withings: Mapped["WithingsUser"] = relationship(
        back_populates="user", lazy="joined", join_depth=2
    )
    fitbit: Mapped["FitbitUser"] = relationship(
        back_populates="user", lazy="joined", join_depth=2
    )


class WithingsUser(TimestampMixin, Base):
    __tablename__ = "withings_users"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    user: Mapped["User"] = relationship(
        back_populates="withings", lazy="joined", join_depth=2
    )
    oauth_access_token: Mapped[Optional[str]] = mapped_column(String(40))
    oauth_refresh_token: Mapped[Optional[str]] = mapped_column(String(40))
    oauth_userid: Mapped[str] = mapped_column(String(40))
    oauth_expiration_date: Mapped[Optional[datetime]] = mapped_column()
    last_weight: Mapped[Optional[float]] = mapped_column(Float())


class FitbitUser(TimestampMixin, Base):
    __tablename__ = "fitbit_users"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    user: Mapped["User"] = relationship(
        back_populates="fitbit", lazy="joined", join_depth=2
    )
    oauth_access_token: Mapped[Optional[str]] = mapped_column(String(512))
    oauth_refresh_token: Mapped[Optional[str]] = mapped_column(String(512))
    oauth_userid: Mapped[str] = mapped_column(String(40))
    oauth_expiration_date: Mapped[Optional[datetime]] = mapped_column()
    fitbit_user_id: Mapped[Optional[str]] = mapped_column(String(40))
    health_user_id: Mapped[Optional[str]] = mapped_column(String(63))
    last_sleep_start_time: Mapped[Optional[datetime]] = mapped_column()
    last_sleep_end_time: Mapped[Optional[datetime]] = mapped_column()
    last_sleep_sleep_minutes: Mapped[Optional[int]] = mapped_column()
    last_sleep_wake_minutes: Mapped[Optional[int]] = mapped_column()

    @property
    def lookup(self) -> UserLookup:
        if self.health_user_id:
            return HealthUserLookup(user_id=self.health_user_id)
        # We should have a fitbit_user_id if we don't have a health_user_id.
        # No need to handle the case where both are None. Shouldn't happen!
        return FitbitUserLookup(user_id=self.fitbit_user_id)


class FitbitActivity(TimestampMixin, Base):
    __tablename__ = "fitbit_activities"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    log_id: Mapped[str] = mapped_column(String(80), unique=True)
    type_id: Mapped[int] = mapped_column()
    logged_at: Mapped[datetime] = mapped_column()
    total_minutes: Mapped[int] = mapped_column()
    calories: Mapped[int] = mapped_column()
    distance_km: Mapped[Optional[float]] = mapped_column()
    fat_burn_minutes: Mapped[Optional[int]] = mapped_column()
    cardio_minutes: Mapped[Optional[int]] = mapped_column()
    peak_minutes: Mapped[Optional[int]] = mapped_column()
    out_of_zone_minutes: Mapped[Optional[int]] = mapped_column()
    fitbit_user_id: Mapped[int] = mapped_column(
        ForeignKey("fitbit_users.id", ondelete="CASCADE")
    )


class DistanceAccount(TimestampMixin, Base):
    __tablename__ = "distance_account"
    # https://docs.sqlalchemy.org/en/21/orm/declarative_tables.html#declarative-table-configuration
    __table_args__ = (
        UniqueConstraint(
            "fitbit_user_id",
            "type_id",
            "date",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    fitbit_user_id: Mapped[int] = mapped_column(
        ForeignKey("fitbit_users.id", ondelete="CASCADE")
    )
    type_id: Mapped[int] = mapped_column()
    date: Mapped[dt_date] = mapped_column()
    credit_km: Mapped[Optional[float]] = mapped_column()
    debit_km: Mapped[Optional[float]] = mapped_column()


class FitbitDailyActivity(Base):
    __tablename__ = "fitbit_daily_activities"
    __table_args__ = {"info": {"is_view": True}}
    fitbit_user_id: Mapped[int] = mapped_column(
        ForeignKey("fitbit_users.id"),
        primary_key=True,
    )
    fitbit_user: Mapped["FitbitUser"] = relationship(lazy="joined", join_depth=2)
    type_id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[dt_date] = mapped_column(primary_key=True)
    count_activities: Mapped[int] = mapped_column()
    sum_calories: Mapped[int] = mapped_column()
    sum_distance_km: Mapped[float] = mapped_column()
    sum_total_minutes: Mapped[int] = mapped_column()
    sum_fat_burn_minutes: Mapped[Optional[int]] = mapped_column()
    sum_cardio_minutes: Mapped[Optional[int]] = mapped_column()
    sum_peak_minutes: Mapped[Optional[int]] = mapped_column()
    sum_out_of_zone_minutes: Mapped[Optional[int]] = mapped_column()

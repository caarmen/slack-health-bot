import dataclasses
import datetime as dt
from enum import StrEnum, auto


class ActivityZone(StrEnum):
    PEAK = auto()
    CARDIO = auto()
    FAT_BURN = auto()
    OUT_OF_ZONE = auto()


@dataclasses.dataclass
class ActivityZoneMinutes:
    zone: ActivityZone
    minutes: int


@dataclasses.dataclass
class ActivityData:
    log_id: int
    type_id: int
    total_minutes: int
    calories: int
    distance_km: float | None
    zone_minutes: list[ActivityZoneMinutes]


@dataclasses.dataclass
class TopActivityStats:
    top_calories: int | None
    top_distance_km: float | None
    top_total_minutes: int | None
    top_zone_minutes: list[ActivityZoneMinutes]


@dataclasses.dataclass
class ActivityHistory:
    latest_activity_data: ActivityData | None
    new_activity_data: ActivityData
    all_time_top_activity_data: TopActivityStats
    recent_top_activity_data: TopActivityStats


@dataclasses.dataclass
class DailyActivityStats:
    date: dt.date
    fitbit_userid: int
    slack_alias: str
    type_id: int
    count_activities: int
    sum_calories: int
    sum_distance_km: float | None
    sum_total_minutes: int
    sum_fat_burn_minutes: int | None
    sum_cardio_minutes: int | None
    sum_peak_minutes: int | None
    sum_out_of_zone_minutes: int | None


@dataclasses.dataclass
class TopDailyActivityStats:
    top_count_activities: int
    top_sum_calories: int
    top_sum_distance_km: float | None
    top_sum_total_minutes: int
    top_sum_fat_burn_minutes: int | None
    top_sum_cardio_minutes: int | None
    top_sum_peak_minutes: int | None
    top_sum_out_of_zone_minutes: int | None


@dataclasses.dataclass
class DailyActivityHistory:
    previous_daily_activity_stats: DailyActivityStats | None
    new_daily_activity_stats: DailyActivityStats | None
    all_time_top_daily_activity_stats: TopDailyActivityStats
    recent_top_daily_activity_stats: TopDailyActivityStats

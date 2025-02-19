import dataclasses
import datetime as dt
import enum
import os
from copy import deepcopy
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional

import yaml
from pydantic import AnyHttpUrl, BaseModel, HttpUrl
from pydantic.v1.utils import deep_update
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


@dataclasses.dataclass
class WithingsOAuthSettings:
    name = "withings"
    base_url: str
    oauth_scopes: list[str]
    callback_url: str
    redirect_uri: str


@dataclasses.dataclass
class FitbitOAuthSettings:
    name = "fitbit"
    base_url: str
    oauth_scopes: list[str]
    subscriber_verification_code: str


class Poll(BaseModel):
    enabled: bool = True
    interval_seconds: int = 3600


class ReportField(enum.StrEnum):
    activity_count = enum.auto()
    distance = enum.auto()
    calories = enum.auto()
    duration = enum.auto()
    fat_burn_minutes = enum.auto()
    cardio_minutes = enum.auto()
    peak_minutes = enum.auto()
    out_of_zone_minutes = enum.auto()


class Goals(BaseModel):
    distance_km: float | None = None


class Report(BaseModel):
    daily: bool
    realtime: bool
    fields: Optional[list[ReportField]] = None
    daily_goals: Goals | None = None


class ActivityType(BaseModel):
    name: str
    id: int
    report: Report | None = None


class Activities(BaseModel):
    daily_report_time: dt.time = dt.time(hour=23, second=50)
    history_days: int = 180
    activity_types: list[ActivityType]
    default_report: Report = Report(
        daily=False,
        realtime=True,
        fields=[x for x in ReportField],
    )

    def get_activity_type(self, id: int) -> ActivityType | None:
        return next((x for x in self.activity_types if x.id == id), None)

    def get_report(self, activity_type_id: int) -> Report | None:
        """
        Get the report configuration for the given activity type.
        If the activity type doesn't have an explicit report configuration,
        fallback to the default report configuration.

        If the activity type report configuration is missing some attributes,
        fill them in with the default report configuration. This applies to the
        following attributes:
        - fields

        :return None: If the activity type id is unknown
        """
        activity_type = self.get_activity_type(id=activity_type_id)
        if not activity_type:
            return None

        if activity_type.report is None:
            return self.default_report

        report = deepcopy(activity_type.report)
        if not report.fields:
            report.fields = self.default_report.fields

        return report

    @property
    def daily_activity_type_ids(self) -> list[int]:
        return [
            x.id
            for x in self.activity_types
            if (
                (x.report and x.report.daily)
                or (x.report is None and self.default_report.daily)
            )
        ]


class Fitbit(BaseModel):
    poll: Poll
    activities: Activities
    base_url: str = "https://api.fitbit.com/"
    oauth_scopes: list[str] = ["sleep", "activity"]


class Withings(BaseModel):
    callback_url: AnyHttpUrl
    base_url: str = "https://wbsapi.withings.net/"
    oauth_scopes: list[str] = ["user.metrics", "user.activity"]


class Logging(BaseModel):
    sql_log_level: str = "WARNING"


class AppSettings(BaseSettings):
    server_url: AnyHttpUrl
    request_timeout_s: float
    database_path: Path = "/tmp/data/slackhealthbot.db"
    logging: Logging
    withings: Withings
    fitbit: Fitbit
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
    )

    @classmethod
    def _load_yaml_file(
        cls,
        path: str,
        required: bool,
    ) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as file:
                return yaml.safe_load(file)
        except OSError as e:
            if required:
                raise e
            return {}

    @classmethod
    def _load_merged_config(cls) -> dict:
        default_config = cls._load_yaml_file("config/app-default.yaml", required=True)
        custom_config = cls._load_yaml_file(
            os.environ.get("SHB_CUSTOM_CONFIG_PATH", "config/app-custom.yaml"),
            required=False,
        )
        return deep_update(default_config, custom_config)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: BaseSettings,
        *,
        env_settings: PydanticBaseSettingsSource,
        **kwargs,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        merged_config = cls._load_merged_config()
        with NamedTemporaryFile(mode="w") as file:
            yaml.safe_dump(merged_config, file.file)
            yaml_settings_source = YamlConfigSettingsSource(
                settings_cls,
                yaml_file=file.name,
            )
        return (env_settings, yaml_settings_source)


class SecretSettings(BaseSettings):
    withings_client_secret: str
    withings_client_id: str
    fitbit_client_id: str
    fitbit_client_secret: str
    fitbit_client_subscriber_verification_code: str
    slack_webhook_url: HttpUrl
    model_config = SettingsConfigDict(env_file=".env")


@dataclasses.dataclass
class Settings:
    app_settings: AppSettings
    secret_settings: SecretSettings

    @property
    def withings_oauth_settings(self):
        return WithingsOAuthSettings(
            base_url=self.app_settings.withings.base_url,
            oauth_scopes=self.app_settings.withings.oauth_scopes,
            callback_url=self.app_settings.withings.callback_url,
            redirect_uri=f"{self.app_settings.withings.callback_url}withings-oauth-webhook/",
        )

    @property
    def fitbit_oauth_settings(self):
        return FitbitOAuthSettings(
            base_url=self.app_settings.fitbit.base_url,
            oauth_scopes=self.app_settings.fitbit.oauth_scopes,
            subscriber_verification_code=self.secret_settings.fitbit_client_subscriber_verification_code,
        )

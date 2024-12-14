import dataclasses
import datetime as dt
from pathlib import Path

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


class ActivityType(BaseModel):
    name: str
    id: int
    report_daily: bool = False
    report_realtime: bool = True


class Activities(BaseModel):
    daily_report_time: dt.time = dt.time(hour=23, second=50)
    history_days: int = 180
    activity_types: list[ActivityType]


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
    database_path: Path = "/tmp/data/slackhealthbot.db"
    logging: Logging
    withings: Withings
    fitbit: Fitbit
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        yaml_file="config/app-merged.yaml",
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
        custom_config = cls._load_yaml_file("config/app-custom.yaml", required=False)
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
        with open("config/app-merged.yaml", "w", encoding="utf-8") as file:
            yaml.safe_dump(merged_config, file)
        yaml_settings_source = YamlConfigSettingsSource(settings_cls)
        return (env_settings, yaml_settings_source)

    @property
    def fitbit_realtime_activity_type_ids(self) -> list[int]:
        return [
            x.id for x in self.fitbit.activities.activity_types if x.report_realtime
        ]

    @property
    def fitbit_daily_activity_type_ids(self) -> list[int]:
        return [x.id for x in self.fitbit.activities.activity_types if x.report_daily]

    @property
    def fitbit_activity_type_ids(self) -> list[int]:
        return (
            self.fitbit_realtime_activity_type_ids + self.fitbit_daily_activity_type_ids
        )


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

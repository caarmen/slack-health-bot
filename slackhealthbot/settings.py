import dataclasses
import datetime as dt
from pathlib import Path

from pydantic import AnyHttpUrl, BaseModel, HttpUrl
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


class App(BaseModel):
    server_url: AnyHttpUrl
    database_path: Path = "/tmp/data/slackhealthbot.db"
    logging: Logging


class AppSettings(BaseSettings):
    app: App
    withings: Withings
    fitbit: Fitbit
    model_config = SettingsConfigDict(yaml_file="config/app.yaml")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: BaseSettings,
        *args,
        **kwargs,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        yaml_settings_source = YamlConfigSettingsSource(settings_cls)
        return (yaml_settings_source,)


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

    @property
    def fitbit_realtime_activity_type_ids(self) -> list[int]:
        return [
            x.id
            for x in self.app_settings.fitbit.activities.activity_types
            if x.report_realtime
        ]

    @property
    def fitbit_daily_activity_type_ids(self) -> list[int]:
        return [
            x.id
            for x in self.app_settings.fitbit.activities.activity_types
            if x.report_daily
        ]

    @property
    def fitbit_activity_type_ids(self) -> list[int]:
        return (
            self.fitbit_realtime_activity_type_ids + self.fitbit_daily_activity_type_ids
        )


settings = Settings(
    app_settings=AppSettings(),
    secret_settings=SecretSettings(),
)
withings_oauth_settings = settings.withings_oauth_settings
fitbit_oauth_settings = settings.fitbit_oauth_settings

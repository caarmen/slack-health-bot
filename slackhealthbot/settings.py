import dataclasses
import datetime as dt
from pathlib import Path

from pydantic import AnyHttpUrl, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


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


class Settings(BaseSettings):
    database_path: Path = "/tmp/data/slackhealthbot.db"
    server_url: AnyHttpUrl
    withings_base_url: str = "https://wbsapi.withings.net/"
    withings_oauth_scopes: list[str] = ["user.metrics", "user.activity"]
    withings_client_secret: str
    withings_client_id: str
    withings_callback_url: AnyHttpUrl
    fitbit_base_url: str = "https://api.fitbit.com/"
    fitbit_oauth_scopes: list[str] = ["sleep", "activity"]
    fitbit_client_id: str
    fitbit_client_secret: str
    fitbit_client_subscriber_verification_code: str
    fitbit_poll_interval_s: int = 3600
    fitbit_poll_enabled: bool = True
    fitbit_realtime_activity_type_ids: list[int] = [
        # See https://dev.fitbit.com/build/reference/web-api/activity/get-all-activity-types/
        # for the list of all supported activity types and their ids
        55001,  # Spinning
        90013,  # Walk
        # 90001,  # Bike
        # 90019,  # Treadmill
        # 1071,   # Outdoor Bike
    ]
    fitbit_daily_activity_type_ids: list[int] = [
        90019,
    ]
    fitbit_daily_activity_post_time: dt.time = dt.time(hour=23, second=50)
    fitbit_activity_record_history_days: int = 180
    slack_webhook_url: HttpUrl
    sql_log_level: str = "WARNING"
    model_config = SettingsConfigDict(env_file=".env")

    @property
    def withings_oauth_settings(self):
        return WithingsOAuthSettings(
            base_url=self.withings_base_url,
            oauth_scopes=self.withings_oauth_scopes,
            callback_url=self.withings_callback_url,
            redirect_uri=f"{self.withings_callback_url}withings-oauth-webhook/",
        )

    @property
    def fitbit_oauth_settings(self):
        return FitbitOAuthSettings(
            base_url=self.fitbit_base_url,
            oauth_scopes=self.fitbit_oauth_scopes,
            subscriber_verification_code=self.fitbit_client_subscriber_verification_code,
        )

    @property
    def fitbit_activity_type_ids(self) -> list[int]:
        return (
            self.fitbit_realtime_activity_type_ids + self.fitbit_daily_activity_type_ids
        )


settings = Settings()
withings_oauth_settings = settings.withings_oauth_settings
fitbit_oauth_settings = settings.fitbit_oauth_settings

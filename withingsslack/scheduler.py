from threading import Timer
import datetime
from typing import Optional
from withingsslack.services.exceptions import UserLoggedOutException
from withingsslack.services.models import SleepData
from withingsslack.settings import settings
from withingsslack.services.fitbit import api as fitbit_api
from withingsslack.database.connection import SessionLocal
from withingsslack.database import models
from withingsslack.services import slack
import logging

_cache_success: dict[str, datetime.date] = {}
_cache_fail: dict[str, datetime.date] = {}


def handle_success_poll(
    fitbit_user: models.FitbitUser,
    sleep_data: Optional[SleepData],
    when: datetime.date,
):
    if sleep_data:
        slack.post_sleep(sleep_data)
        _cache_success[fitbit_user.oauth_userid] = when
        _cache_fail.pop(fitbit_user.oauth_userid, None)


def handle_fail_poll(
    fitbit_user: models.FitbitUser,
    when: datetime.date,
):
    last_error_post = _cache_fail.get(fitbit_user.oauth_userid)
    if not last_error_post or last_error_post < when:
        slack.post_user_logged_out(
            slack_alias=fitbit_user.user.slack_alias,
            service="fitbit",
        )
        _cache_fail[fitbit_user.oauth_userid] = when


def fitbit_poll():
    logging.info("fitbit poll")
    with SessionLocal() as db:
        fitbit_users = db.query(models.FitbitUser).all()
        today = datetime.date.today()
        for fitbit_user in fitbit_users:
            latest_successful_poll = _cache_success.get(fitbit_user.oauth_userid)
            if not latest_successful_poll or latest_successful_poll < today:
                try:
                    sleep_data = fitbit_api.get_sleep(
                        db,
                        userid=fitbit_user.oauth_userid,
                        when=today,
                    )
                except UserLoggedOutException:
                    handle_fail_poll(fitbit_user=fitbit_user, when=today)
                else:
                    handle_success_poll(
                        fitbit_user=fitbit_user, sleep_data=sleep_data, when=today
                    )
    schedule_fitbit_poll()


def schedule_fitbit_poll(delay_s: int = settings.fitbit_poll_interval_s):
    timer = Timer(delay_s, fitbit_poll)
    timer.daemon = True
    timer.start()

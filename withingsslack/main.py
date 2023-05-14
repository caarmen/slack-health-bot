import logging
from typing import Annotated, Optional

import datetime
import uvicorn
from fastapi import Depends, FastAPI, Form, Response, status
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from withingsslack import logger, scheduler
from withingsslack.database import crud
from withingsslack.database.connection import SessionLocal
from withingsslack.services import slack
from withingsslack.services.exceptions import UserLoggedOutException
from withingsslack.services.withings import api as withings_api
from withingsslack.services.fitbit import api as fitbit_api
from withingsslack.services.withings import oauth as withings_oauth
from withingsslack.services.fitbit import oauth as fitbit_oauth
from starlette.middleware import Middleware


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app = FastAPI(
    middleware=[Middleware(logger.LoggerMiddleware)],
)


@app.get("/v1/withings-authorization/{slack_alias}")
def get_withings_authorization(slack_alias: str):
    return RedirectResponse(
        url=withings_oauth.create_oauth_url(slack_alias=slack_alias)
    )


@app.get("/v1/fitbit-authorization/{slack_alias}")
def get_fitbit_authorization(slack_alias: str):
    return RedirectResponse(url=fitbit_oauth.create_oauth_url(slack_alias=slack_alias))


@app.head("/")
def validate_root():
    return Response()


@app.head("/withings-oauth-webhook/")
def validate_oauth_webhook():
    return Response()


@app.head("/withings-notification-webhook/")
def validate_notification_webhook():
    return Response()


@app.get("/fitbit-oauth-webhook/")
def fitbit_oauth_webhook(code: str, state: str, db: Session = Depends(get_db)):
    user = fitbit_oauth.fetch_token(db=db, code=code, state=state)
    fitbit_api.subscribe(db, user)
    html_content = """
    <html>
        <head>
            <title>Fitbit login complete</title>
        </head>
        <body>
            <h1>Congrats, Fitbit login complete</h1>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)


@app.get("/withings-oauth-webhook/")
def withings_oauth_webhook(code: str, state: str, db: Session = Depends(get_db)):
    user = withings_oauth.fetch_token(db=db, state=state, code=code)
    withings_api.subscribe(db, user)
    html_content = """
    <html>
        <head>
            <title>Login complete</title>
        </head>
        <body>
            <h1>Congrats, login complete</h1>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)


class FitbitNotification(BaseModel):
    collectionType: Optional[str]
    date: Optional[datetime.date]
    ownerId: Optional[str]
    ownerType: Optional[str]
    subscriptionId: Optional[str]


@app.post("/fitbit-notification-webhook/")
def fitbit_notification_webhook(
    notifications: list[FitbitNotification],
    db: Session = Depends(get_db),
):
    logging.info(f"fitbit_notification_webhook: {notifications}")
    notification = next(
        (n for n in notifications if n.collectionType == "sleep" and n.ownerId), None
    )
    if notification:
        sleep_data = fitbit_api.get_sleep(
            db,
            userid=notification.ownerId,
            when=notification.date,
        )
        if sleep_data:
            slack.post_sleep(sleep_data)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


last_processed_notification_per_user = {}


@app.post("/withings-notification-webhook/")
def withings_notification_webhook(
    userid: Annotated[str, Form()],
    startdate: Annotated[int, Form()],
    enddate: Annotated[int, Form()],
    db: Session = Depends(get_db),
):
    logging.info(
        "withings_notification_webhook: "
        + f"userid={userid}, startdate={startdate}, enddate={enddate}"
    )
    if last_processed_notification_per_user.get(userid, None) != (startdate, enddate):
        try:
            last_weight_data = withings_api.get_last_weight(
                db,
                userid=userid,
                startdate=startdate,
                enddate=enddate,
            )
        except UserLoggedOutException:
            user = crud.get_user(db, withings_oauth_userid=userid)
            slack.post_user_logged_out(
                slack_alias=user.slack_alias,
                service="withings",
            )
        else:
            if last_weight_data:
                slack.post_weight(last_weight_data)
                last_processed_notification_per_user[userid] = (startdate, enddate)
    else:
        logging.info("Ignoring duplicate withings notification")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


scheduler.schedule_fitbit_poll(delay_s=10)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_config=logger.get_uvicorn_log_config(),
    )

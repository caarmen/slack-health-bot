# slack-health-bot: Slack notifications for limited Withings and Fitbit data

Pushes messages to a pre-selected Slack channel, when users log new weight data in Withings or new sleep or activity data in Fitbit.

[![GitHub Workflow Status (with branch)](https://img.shields.io/github/actions/workflow/status/caarmen/slack-health-bot/check.yml)](https://github.com/caarmen/slack-health-bot/actions/workflows/check.yml?query=branch%3Amain)
[![GitHub](https://img.shields.io/github/license/caarmen/slack-health-bot)](https://github.com/caarmen/slack-health-bot/blob/main/LICENSE)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/caarmen/slack-health-bot)](https://github.com/caarmen/slack-health-bot/releases)

[![GitHub repo size](https://img.shields.io/github/repo-size/caarmen/slack-health-bot)](https://github.com/caarmen/slack-health-bot/archive/refs/heads/main.zip)
![GitHub language count](https://img.shields.io/github/languages/count/caarmen/slack-health-bot)
[![GitHub Release Date](https://img.shields.io/github/release-date/caarmen/slack-health-bot)](https://github.com/caarmen/slack-health-bot/releases)
[![GitHub commit activity](https://img.shields.io/github/commit-activity/m/caarmen/slack-health-bot)](https://github.com/caarmen/slack-health-bot/commits/main)
[![GitHub last commit](https://img.shields.io/github/last-commit/caarmen/slack-health-bot)](https://github.com/caarmen/slack-health-bot/commits/main)

[![GitHub Repo stars](https://img.shields.io/github/stars/caarmen/slack-health-bot?style=social)](https://github.com/caarmen/slack-health-bot/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/caarmen/slack-health-bot?style=social)](https://github.com/caarmen/slack-health-bot/forks)

## Configuration

* Create an application in the [Withings developer dashboard](https://developer.withings.com/dashboard/).
* Create an application in the [Fitbit developer dashboard](https://dev.fitbit.com/apps/).
* Create an application [on Slack](https://api.slack.com/apps), with a webhook to post messages to a specific channel.
* Copy the `.env.template` file to `.env`, and modify the values.
* [Optional]: Copy the `config/app-custom.yaml.template` file to `app-custom.yaml`, and override any values which are defined in `config/app-default.yaml`.

## Retrieve the docker image

Retrieve the image:
```
docker pull ghcr.io/caarmen/slack-health-bot:latest
```

## Run the docker image

Create a folder on the host where the database will be saved: `/path/to/data/`.

Run the docker image.

```
docker run --detach --publish 8000:8000 -v `pwd`/.env:/app/.env -v `pwd`/app-custom.yaml:/app/config/app-custom.yaml  -v /path/to/data/:/tmp/data ghcr.io/caarmen/slack-health-bot
```

## Using the application

### Withings
* Open the following url in a browser: http://your-server/v1/withings-authorization/your-slack-alias
  - Change `your-server` with the address on which the server is available.
  - Change `your-slack-alias` with your slack username.
* Authorize the app in the Withings screen.
* Log a new weight measurement in your Withings account.
  - After a couple of minutes, you should see a message in the configured slack channel saying:
    > New weight from @`your-slack-alias`: XX kg

#### Forcing a measurement to be pushed to slack
You can force a measurement to be posted to slack, by simulating Withings calling the webhook:
```
curl --location 'http://your-server/withings-notification-webhook/' \
--form 'userid="1234567"' \
--form 'startdate="1680377444"' \
--form 'enddate="1682969444"'
```

### Fitbit
* Open the following url in a browser: http://your-server/v1/fitbit-authorization/your-slack-alias
  - Change `your-server` with the address on which the server is available.
  - Change `your-slack-alias` with your slack username.
* Authorize the app in the Fitbit screen.
* Log a new sleep measurement or activity in your Fitbit account.
  - After the polling period (if polling is enabled), or after a the webhook is called,
    you should see a message in the configured slack channel saying (for the sleep example):
    > New sleep from @`your-slack-alias`:
    >
    > • Went to bed at 22:17
    >
    > • Woke up at 7:59
    >
    > • Total sleep: 8h 31m
    >
    > • Awake: 1h 11m
    >
    > • Score: 96

You can find your userid in the database file:
```
sqlite3 -header -column /path/to/slackhealthbot.db \
  "select
     slack_alias,
     withings_users.oauth_userid as withings_userid,
     fitbit_users.oauth_userid as fitbit_userid
  from users
    left outer join withings_users on users.id = withings_users.user_id
    left outer join fitbit_users on users.id = fitbit_users.user_id;"
```

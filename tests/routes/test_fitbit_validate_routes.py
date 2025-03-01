import dataclasses
from typing import Callable

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from slackhealthbot.settings import Settings


@dataclasses.dataclass
class Scenario:
    name: str
    input_verify_value: Callable[[Settings], str]
    expected_response_status_code: int


SCENARIOS = [
    Scenario(
        name="valid verify code",
        input_verify_value=lambda settings: settings.secret_settings.fitbit_client_subscriber_verification_code,
        expected_response_status_code=status.HTTP_204_NO_CONTENT,
    ),
    Scenario(
        name="invalid verify code",
        input_verify_value=lambda _: "invalid code",
        expected_response_status_code=status.HTTP_404_NOT_FOUND,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ids=[x.name for x in SCENARIOS],
    argnames=["scenario"],
    argvalues=[[x] for x in SCENARIOS],
)
async def test_validate_fitbit_notification_webhook(
    client: TestClient,
    scenario: Scenario,
    settings: Settings,
):
    # When we receive the callback from fitbit to validate the notification webhook
    response = client.get(
        "/fitbit-notification-webhook/",
        params={
            "verify": scenario.input_verify_value(settings),
        },
    )

    assert response.status_code == scenario.expected_response_status_code

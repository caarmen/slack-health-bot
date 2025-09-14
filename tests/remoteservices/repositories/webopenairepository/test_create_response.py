import dataclasses

import pytest
from httpx import Response
from respx import MockRouter

from slackhealthbot.main import app
from slackhealthbot.remoteservices.repositories.webopenairepository import (
    WebOpenAiRepository,
)
from slackhealthbot.settings import SecretSettings, Settings


def _create_web_openai_repository(api_key: str | None) -> WebOpenAiRepository:
    orig_settings: Settings = app.container.settings.provided()
    mock_settings = Settings(
        app_settings=orig_settings.app_settings,
        secret_settings=SecretSettings(openai_api_key=api_key),
    )
    return WebOpenAiRepository(mock_settings)


@pytest.mark.asyncio
async def test_openai_key_not_configured(
    respx_mock: MockRouter,
):
    """
    Given the settings without an openai key configured
    When the method to create a motivational message is called
    Then no call is done to OpenAI
    And None is returned.
    """

    # Given the settings without an openai key configured
    repo = _create_web_openai_repository(None)
    mock_openapi = respx_mock.post("https://api.openai.com/v1/responses").mock(
        return_value=Response(
            status_code=200,
            json={"doesnt": "matter"},
        )
    )

    # When the method to create a motivational message is called
    actual_message = await repo.create_response("some prompt")

    # Then no call is done to OpenAI
    assert not mock_openapi.called

    # And None is returned.
    assert actual_message is None


@pytest.mark.asyncio
async def test_openai_key_incorrect(
    respx_mock: MockRouter,
):
    """
    Given the settings with a bad api key configured.
    When the method to create a motivational message is called
    Then a call is done to OpenAI
    And None is returned.
    """
    # Given the settings with a bad api key configured.
    repo = _create_web_openai_repository("bad key")
    pass_through_openapi = respx_mock.post(
        "https://api.openai.com/v1/responses"
    ).pass_through()

    # When the method to create a motivational message is called
    actual_message = await repo.create_response("some prompt")

    # Then a call is done to OpenAI
    assert pass_through_openapi.called

    # And None is returned.
    assert actual_message is None


@pytest.mark.asyncio
async def test_openai_ok(
    respx_mock: MockRouter,
):
    """
    Given the settings with a good api key configured.
    When the method to create a motivational message is called
    Then a call is done to OpenAI
    And OpenAI returns with a motivational message
    And the motivational message is returned.
    """
    # Given the settings with a good api key configured.
    repo = _create_web_openai_repository("good key")

    # And OpenAI returns with a motivational message
    # Mock an openai response
    # https://platform.openai.com/docs/api-reference/responses/create
    mock_openai = respx_mock.post("https://api.openai.com/v1/responses").mock(
        return_value=Response(
            status_code=200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "Here is your nice motivational message",
                            }
                        ],
                    }
                ],
            },
        )
    )

    # When the method to create a motivational message is called
    actual_message = await repo.create_response("some prompt")

    # Then a call is done to OpenAI
    assert mock_openai.called

    # And the motivational message is returned.
    assert actual_message == "Here is your nice motivational message"


@pytest.mark.asyncio
async def test_openai_error(
    respx_mock: MockRouter,
):
    """
    Given the settings with a good api key configured.
    And OpenAI is down
    When the method to create a motivational message is called
    Then a call is done to OpenAI
    And None is returned
    """
    # Given the settings with a good api key configured.
    repo = _create_web_openai_repository("good key")

    # And OpenAI is down
    # Mock an openai unavailable response
    # https://platform.openai.com/docs/api-reference/responses/create
    mock_openai = respx_mock.post("https://api.openai.com/v1/responses").mock(
        return_value=Response(
            status_code=503,
        )
    )

    # When the method to create a motivational message is called
    actual_message = await repo.create_response("some prompt")

    # Then a call is done to OpenAI
    assert mock_openai.called

    # And None is returned
    assert actual_message is None


@dataclasses.dataclass
class UnparseableResponseScenario:
    id: str
    response: Response


UNPARSEABLE_RESPONSE_SCENARIOS = [
    UnparseableResponseScenario(
        id="Json without expected fields",
        response=Response(status_code=200, json={"foo": 42}),
    ),
    UnparseableResponseScenario(
        id="Not json response", response=Response(status_code=200, html="<b>oops</b>")
    ),
]


@pytest.mark.parametrize(
    ids=lambda x: x.id,
    argnames="scenario",
    argvalues=UNPARSEABLE_RESPONSE_SCENARIOS,
)
@pytest.mark.asyncio
async def test_openai_unparseable_result(
    respx_mock: MockRouter,
    scenario: UnparseableResponseScenario,
):
    """
    Given the settings with a good api key configured.
    And OpenAI is returning bad responses
    When the method to create a motivational message is called
    Then a call is done to OpenAI
    And None is returned
    """
    # Given the settings with a good api key configured.
    repo = _create_web_openai_repository("good key")

    # And OpenAI is returning bad responses
    # Mock an openai response
    # https://platform.openai.com/docs/api-reference/responses/create
    mock_openai = respx_mock.post("https://api.openai.com/v1/responses").mock(
        return_value=scenario.response,
    )

    # When the method to create a motivational message is called
    actual_message = await repo.create_response("some prompt")

    # Then a call is done to OpenAI
    assert mock_openai.called

    # And None is returned
    assert actual_message is None

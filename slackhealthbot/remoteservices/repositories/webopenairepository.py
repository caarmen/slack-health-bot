import logging

from openai import AsyncOpenAI, OpenAIError
from openai.types.responses import Response

from slackhealthbot.domain.remoterepository.remoteopenairepository import (
    RemoteOpenAiRepository,
)
from slackhealthbot.settings import Settings

logger = logging.getLogger(__name__)


class WebOpenAiRepository(RemoteOpenAiRepository):
    def __init__(
        self,
        settings: Settings,
    ):
        super().__init__()
        self.api_key = settings.secret_settings.openai_api_key
        self.model_name = settings.app_settings.openai.model

    async def create_response(self, prompt: str) -> str | None:
        """
        :return: a response for the given prompt,
            None if openai_api_key hasn't been configured,
            None if the openai client returned an error.
        """
        if self.api_key is None:
            return None

        client = AsyncOpenAI(
            api_key=self.api_key,
        )
        try:
            response = await client.responses.create(
                model=self.model_name,
                input=prompt,
            )

            if isinstance(response, Response) and response.output:
                return response.output_text
        except OpenAIError as e:
            logger.warning(f"Error from OpenAi when trying to create response: {e}")
        return None

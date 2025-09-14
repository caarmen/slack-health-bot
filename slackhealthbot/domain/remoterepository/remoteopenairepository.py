from abc import ABC, abstractmethod


class RemoteOpenAiRepository(ABC):
    @abstractmethod
    async def create_response(
        self,
        prompt: str,
    ) -> str:
        """
        :return: a response for the given prompt,
            None if openai_api_key hasn't been configured,
            None if the openai client returned an error.
        """

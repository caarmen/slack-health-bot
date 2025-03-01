import asyncio
from typing import Coroutine

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from respx import Route


async def execute_parallel_requests(
    app: FastAPI,
    request_count: int,
    request_coro: Coroutine[None, AsyncClient, None],
):
    """
    Execute requests in parallel.

    Creates an AsyncClient, and calls the given request_coro the request_count number of times,
    with the AsyncClient, and waits for each request_coro function to complete before returning.
    """

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        async with asyncio.TaskGroup() as tg:
            for _ in range(request_count):
                tg.create_task(request_coro(ac))


def mock_delayed_responses(
    route: Route,
    mock_responses: list[Response],
):
    """
    Mock the given responses for the given route, with a
    distributed delay.

    The first response will arrive with the largest delay,
    and the last response will arrive with no delay.

    This is to be used with execute_parallel_requests.
    Without this, if the route for the parallel requests executes
    itself an http request (the ones mocked here), there will be no
    opportunity for context switching, and the requests will be executed
    in a sequential way.
    """

    def delayed_response_side_effect(
        delay_s: float,
        response: Response,
    ):
        async def side_effect(request):
            await asyncio.sleep(delay=delay_s)
            return response

        return side_effect

    request_count = len(mock_responses)
    route.side_effect = [
        delayed_response_side_effect(
            float(request_count - x) / request_count, response=mock_responses[x]
        )
        for x in range(request_count)
    ]

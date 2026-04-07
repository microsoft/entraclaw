"""Graph API 429 rate-limit retry transport for httpx.

Wraps an ``httpx.AsyncBaseTransport`` and automatically retries requests
that receive a 429 response, respecting the ``Retry-After`` header.

Usage in teams.py (or any module making Graph calls)::

    transport = RetryOn429Transport(wrapped=httpx.AsyncHTTPTransport())
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await client.get(...)
"""

from __future__ import annotations

import asyncio
import logging

import httpx

logger = logging.getLogger("entraclaw.tools.rate_limit")

DEFAULT_RETRY_AFTER = 5  # seconds when Retry-After header is missing
DEFAULT_MAX_RETRIES = 3
DEFAULT_MAX_WAIT = 120  # cap on Retry-After to avoid absurd waits


class RetryOn429Transport(httpx.AsyncBaseTransport):
    """Async httpx transport that retries on 429 with Retry-After backoff."""

    def __init__(
        self,
        wrapped: httpx.AsyncBaseTransport,
        max_retries: int = DEFAULT_MAX_RETRIES,
        max_wait: int = DEFAULT_MAX_WAIT,
    ) -> None:
        self._wrapped = wrapped
        self._max_retries = max_retries
        self._max_wait = max_wait

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = await self._wrapped.handle_async_request(request)

        retries = 0
        while response.status_code == 429 and retries < self._max_retries:
            retries += 1
            retry_after = int(response.headers.get("Retry-After", str(DEFAULT_RETRY_AFTER)))
            retry_after = min(retry_after, self._max_wait)

            logger.warning(
                "Graph API 429 — retry %d/%d after %ds",
                retries,
                self._max_retries,
                retry_after,
            )
            await asyncio.sleep(retry_after)
            response = await self._wrapped.handle_async_request(request)

        return response

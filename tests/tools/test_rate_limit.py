"""Tests for Graph API 429 rate-limit retry middleware.

The retry transport wraps httpx and automatically waits + retries
when Graph returns 429 with a Retry-After header.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from entraclaw.tools.rate_limit import RetryOn429Transport


class TestRetryOn429Transport:
    """Test the rate-limit retry transport."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_no_retry_on_success(self) -> None:
        """Normal 200 responses pass through without retry."""
        respx.get("https://graph.microsoft.com/v1.0/me").mock(
            return_value=httpx.Response(200, json={"id": "user-1"})
        )
        transport = RetryOn429Transport(wrapped=httpx.AsyncHTTPTransport())
        async with httpx.AsyncClient(transport=transport) as client:
            resp = await client.get("https://graph.microsoft.com/v1.0/me")
        assert resp.status_code == 200

    @respx.mock
    @pytest.mark.asyncio
    async def test_retries_on_429_then_succeeds(self) -> None:
        """429 followed by 200 — retries once and returns the success."""
        respx.get("https://graph.microsoft.com/v1.0/me").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "0"}),
                httpx.Response(200, json={"id": "user-1"}),
            ]
        )
        transport = RetryOn429Transport(wrapped=httpx.AsyncHTTPTransport())
        async with httpx.AsyncClient(transport=transport) as client:
            resp = await client.get("https://graph.microsoft.com/v1.0/me")
        assert resp.status_code == 200
        assert resp.json()["id"] == "user-1"

    @respx.mock
    @pytest.mark.asyncio
    async def test_gives_up_after_max_retries(self) -> None:
        """If all retries hit 429, the last 429 response is returned."""
        respx.get("https://graph.microsoft.com/v1.0/me").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "0"}),
                httpx.Response(429, headers={"Retry-After": "0"}),
                httpx.Response(429, headers={"Retry-After": "0"}),
                httpx.Response(429, headers={"Retry-After": "0"}),
            ]
        )
        transport = RetryOn429Transport(wrapped=httpx.AsyncHTTPTransport(), max_retries=3)
        async with httpx.AsyncClient(transport=transport) as client:
            resp = await client.get("https://graph.microsoft.com/v1.0/me")
        assert resp.status_code == 429

    @respx.mock
    @pytest.mark.asyncio
    async def test_defaults_retry_after_when_missing(self) -> None:
        """Missing Retry-After header defaults to a short wait, still retries."""
        respx.get("https://graph.microsoft.com/v1.0/me").mock(
            side_effect=[
                httpx.Response(429),  # no Retry-After header
                httpx.Response(200, json={"ok": True}),
            ]
        )
        transport = RetryOn429Transport(wrapped=httpx.AsyncHTTPTransport())
        async with httpx.AsyncClient(transport=transport) as client:
            resp = await client.get("https://graph.microsoft.com/v1.0/me")
        assert resp.status_code == 200

    @respx.mock
    @pytest.mark.asyncio
    async def test_caps_retry_after_at_max(self) -> None:
        """Absurdly large Retry-After values are capped."""
        respx.get("https://graph.microsoft.com/v1.0/me").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "9999"}),
                httpx.Response(200, json={"ok": True}),
            ]
        )
        # max_wait=1 caps to 1s; Retry-After=0 for test speed
        transport = RetryOn429Transport(
            wrapped=httpx.AsyncHTTPTransport(), max_wait=1
        )
        async with httpx.AsyncClient(transport=transport) as client:
            resp = await client.get("https://graph.microsoft.com/v1.0/me")
        assert resp.status_code == 200

    @respx.mock
    @pytest.mark.asyncio
    async def test_post_requests_also_retry(self) -> None:
        """POST requests (like sending messages) also get retry behavior."""
        respx.post("https://graph.microsoft.com/v1.0/chats/c1/messages").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "0"}),
                httpx.Response(201, json={"id": "msg-1"}),
            ]
        )
        transport = RetryOn429Transport(wrapped=httpx.AsyncHTTPTransport())
        async with httpx.AsyncClient(transport=transport) as client:
            resp = await client.post(
                "https://graph.microsoft.com/v1.0/chats/c1/messages",
                json={"body": {"content": "hi"}},
            )
        assert resp.status_code == 201

    @respx.mock
    @pytest.mark.asyncio
    async def test_non_429_errors_pass_through(self) -> None:
        """Non-429 errors (401, 404, 500) are not retried."""
        respx.get("https://graph.microsoft.com/v1.0/me").mock(
            return_value=httpx.Response(500)
        )
        transport = RetryOn429Transport(wrapped=httpx.AsyncHTTPTransport())
        async with httpx.AsyncClient(transport=transport) as client:
            resp = await client.get("https://graph.microsoft.com/v1.0/me")
        assert resp.status_code == 500

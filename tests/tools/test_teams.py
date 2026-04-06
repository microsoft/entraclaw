"""Tests for Teams connect and send — httpx fully mocked with respx."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from openclaw.errors import (
    ChatNotFound,
    MessageTooLong,
    RateLimitError,
    TeamsNotLicensed,
    TokenExpiredError,
)
from openclaw.tools.teams import GRAPH_BASE, MAX_MESSAGE_LENGTH, connect, send


def _mock_store(token: str = "obo-token", client_id: str = "cid") -> MagicMock:
    store = MagicMock()
    store.retrieve.side_effect = lambda svc, key: {
        "active_client_id": client_id,
        f"{client_id}/obo_token": token,
    }.get(key)
    return store


# ---------------------------------------------------------------------------
# connect
# ---------------------------------------------------------------------------


class TestTeamsConnect:
    @respx.mock
    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        respx.get(f"{GRAPH_BASE}/me").mock(
            return_value=httpx.Response(200, json={"id": "agent-uid"})
        )
        respx.get(f"{GRAPH_BASE}/users/human@example.com").mock(
            return_value=httpx.Response(200, json={"id": "human-uid"})
        )
        respx.post(f"{GRAPH_BASE}/chats").mock(
            return_value=httpx.Response(
                201,
                json={"id": "19:chat-id@thread.v2", "createdDateTime": "2024-01-01"},
            )
        )
        with patch("openclaw.tools.teams.get_credential_store", return_value=_mock_store()):
            result = await connect("human@example.com")
        assert result["chat_id"] == "19:chat-id@thread.v2"

    @respx.mock
    @pytest.mark.asyncio
    async def test_expired_token(self) -> None:
        respx.get(f"{GRAPH_BASE}/me").mock(return_value=httpx.Response(401))
        with (
            patch("openclaw.tools.teams.get_credential_store", return_value=_mock_store()),
            pytest.raises(TokenExpiredError),
        ):
            await connect("human@example.com")

    @respx.mock
    @pytest.mark.asyncio
    async def test_user_not_found(self) -> None:
        respx.get(f"{GRAPH_BASE}/me").mock(return_value=httpx.Response(200, json={"id": "agent"}))
        respx.get(f"{GRAPH_BASE}/users/nobody@example.com").mock(return_value=httpx.Response(404))
        with (
            patch("openclaw.tools.teams.get_credential_store", return_value=_mock_store()),
            pytest.raises(ChatNotFound),
        ):
            await connect("nobody@example.com")

    @respx.mock
    @pytest.mark.asyncio
    async def test_teams_not_licensed(self) -> None:
        respx.get(f"{GRAPH_BASE}/me").mock(return_value=httpx.Response(200, json={"id": "agent"}))
        respx.get(f"{GRAPH_BASE}/users/h@e.com").mock(
            return_value=httpx.Response(200, json={"id": "human"})
        )
        respx.post(f"{GRAPH_BASE}/chats").mock(return_value=httpx.Response(403))
        with (
            patch("openclaw.tools.teams.get_credential_store", return_value=_mock_store()),
            pytest.raises(TeamsNotLicensed),
        ):
            await connect("h@e.com")

    @pytest.mark.asyncio
    async def test_no_active_identity_raises(self) -> None:
        store = MagicMock()
        store.retrieve.return_value = None
        with (
            patch("openclaw.tools.teams.get_credential_store", return_value=store),
            pytest.raises(TokenExpiredError),
        ):
            await connect("anyone@example.com")


# ---------------------------------------------------------------------------
# send
# ---------------------------------------------------------------------------


class TestTeamsSend:
    @respx.mock
    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        respx.post(f"{GRAPH_BASE}/chats/c1/messages").mock(
            return_value=httpx.Response(
                201,
                json={"id": "msg-1", "createdDateTime": "2024-01-01"},
            )
        )
        with patch("openclaw.tools.teams.get_credential_store", return_value=_mock_store()):
            result = await send("c1", "hello!")
        assert result["message_id"] == "msg-1"

    @respx.mock
    @pytest.mark.asyncio
    async def test_html_content(self) -> None:
        route = respx.post(f"{GRAPH_BASE}/chats/c1/messages").mock(
            return_value=httpx.Response(201, json={"id": "msg-2", "createdDateTime": "2024-01-01"})
        )
        with patch("openclaw.tools.teams.get_credential_store", return_value=_mock_store()):
            await send("c1", "<b>hi</b>", content_type="html")
        body = route.calls.last.request.content
        assert b"html" in body

    @pytest.mark.asyncio
    async def test_message_too_long(self) -> None:
        long_msg = "x" * (MAX_MESSAGE_LENGTH + 1)
        with (
            patch("openclaw.tools.teams.get_credential_store", return_value=_mock_store()),
            pytest.raises(MessageTooLong),
        ):
            await send("c1", long_msg)

    @respx.mock
    @pytest.mark.asyncio
    async def test_token_expired(self) -> None:
        respx.post(f"{GRAPH_BASE}/chats/c1/messages").mock(return_value=httpx.Response(401))
        with (
            patch("openclaw.tools.teams.get_credential_store", return_value=_mock_store()),
            pytest.raises(TokenExpiredError),
        ):
            await send("c1", "hello")

    @respx.mock
    @pytest.mark.asyncio
    async def test_rate_limited(self) -> None:
        respx.post(f"{GRAPH_BASE}/chats/c1/messages").mock(
            return_value=httpx.Response(429, headers={"Retry-After": "42"})
        )
        with (
            patch("openclaw.tools.teams.get_credential_store", return_value=_mock_store()),
            pytest.raises(RateLimitError) as exc_info,
        ):
            await send("c1", "hello")
        assert exc_info.value.retry_after == 42

    @respx.mock
    @pytest.mark.asyncio
    async def test_chat_not_found(self) -> None:
        respx.post(f"{GRAPH_BASE}/chats/nope/messages").mock(return_value=httpx.Response(404))
        with (
            patch("openclaw.tools.teams.get_credential_store", return_value=_mock_store()),
            pytest.raises(ChatNotFound),
        ):
            await send("nope", "hello")

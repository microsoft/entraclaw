"""Tests for Teams tools — httpx fully mocked with respx, MSAL mocked.

Token acquisition uses the OBO (On-Behalf-Of) flow:
  1. Retrieve human's refresh token from the OS keychain
  2. Exchange it for a human access token
  3. OBO exchange: human token → agent-attributed token
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from openclaw.errors import (
    AgentIDNotAvailable,
    ChatNotFound,
    MessageTooLong,
    OBOExchangeError,
    RateLimitError,
    TeamsNotLicensed,
    TokenExpiredError,
)
from openclaw.tools.teams import (
    GRAPH_BASE,
    MAX_MESSAGE_LENGTH,
    acquire_agent_token,
    create_or_find_chat,
    read,
    send,
)

# ---------------------------------------------------------------------------
# acquire_agent_token (OBO flow)
# ---------------------------------------------------------------------------


class TestAcquireAgentToken:
    def test_missing_config_raises(self) -> None:
        cleaned = {k: v for k, v in os.environ.items() if not k.startswith("OPENCLAW_")}
        with (
            patch.dict(os.environ, cleaned, clear=True),
            pytest.raises(AgentIDNotAvailable),
        ):
            acquire_agent_token(__import__("openclaw.config", fromlist=["get_config"]).get_config())

    def test_missing_refresh_token_raises(self) -> None:
        env = {
            "OPENCLAW_BLUEPRINT_APP_ID": "bp-id",
            "OPENCLAW_TENANT_ID": "tid",
            "OPENCLAW_BLUEPRINT_SECRET": "secret",
        }
        mock_store = MagicMock()
        mock_store.retrieve.return_value = None
        with (
            patch.dict(os.environ, env, clear=False),
            patch("openclaw.platform.get_credential_store", return_value=mock_store),
            pytest.raises(AgentIDNotAvailable, match="refresh token"),
        ):
            from openclaw.config import get_config

            acquire_agent_token(get_config())

    def test_obo_error_raised(self) -> None:
        env = {
            "OPENCLAW_BLUEPRINT_APP_ID": "bp-id",
            "OPENCLAW_TENANT_ID": "tid",
            "OPENCLAW_BLUEPRINT_SECRET": "secret",
        }
        mock_store = MagicMock()
        mock_store.retrieve.return_value = "cached-refresh-token"

        mock_public_app = MagicMock()
        mock_public_app.get_accounts.return_value = []
        mock_public_app.acquire_token_by_refresh_token.return_value = {
            "access_token": "human-token",
        }

        mock_conf_app = MagicMock()
        mock_conf_app.acquire_token_on_behalf_of.return_value = {
            "error": "interaction_required",
            "error_description": "Consent needed",
        }

        with (
            patch.dict(os.environ, env, clear=False),
            patch("openclaw.platform.get_credential_store", return_value=mock_store),
            patch("openclaw.tools.teams.PublicClientApplication", return_value=mock_public_app),
            patch(
                "openclaw.tools.teams.ConfidentialClientApplication",
                return_value=mock_conf_app,
            ),
            pytest.raises(OBOExchangeError, match="interaction_required"),
        ):
            from openclaw.config import get_config

            acquire_agent_token(get_config())

    def test_success(self) -> None:
        env = {
            "OPENCLAW_BLUEPRINT_APP_ID": "bp-id",
            "OPENCLAW_TENANT_ID": "tid",
            "OPENCLAW_BLUEPRINT_SECRET": "secret",
        }
        mock_store = MagicMock()
        mock_store.retrieve.return_value = "cached-refresh-token"

        mock_public_app = MagicMock()
        mock_public_app.get_accounts.return_value = []
        mock_public_app.acquire_token_by_refresh_token.return_value = {
            "access_token": "human-token",
        }

        mock_conf_app = MagicMock()
        mock_conf_app.acquire_token_on_behalf_of.return_value = {
            "access_token": "agent-obo-token-123",
        }

        with (
            patch.dict(os.environ, env, clear=False),
            patch("openclaw.platform.get_credential_store", return_value=mock_store),
            patch("openclaw.tools.teams.PublicClientApplication", return_value=mock_public_app),
            patch(
                "openclaw.tools.teams.ConfidentialClientApplication",
                return_value=mock_conf_app,
            ),
        ):
            from openclaw.config import get_config

            token = acquire_agent_token(get_config())
        assert token == "agent-obo-token-123"

    def test_human_token_failure_raises_msal_error(self) -> None:
        env = {
            "OPENCLAW_BLUEPRINT_APP_ID": "bp-id",
            "OPENCLAW_TENANT_ID": "tid",
            "OPENCLAW_BLUEPRINT_SECRET": "secret",
        }
        mock_store = MagicMock()
        mock_store.retrieve.return_value = "cached-refresh-token"

        mock_public_app = MagicMock()
        mock_public_app.get_accounts.return_value = []
        mock_public_app.acquire_token_by_refresh_token.return_value = {
            "error": "invalid_grant",
            "error_description": "Refresh token expired",
        }

        with (
            patch.dict(os.environ, env, clear=False),
            patch("openclaw.platform.get_credential_store", return_value=mock_store),
            patch("openclaw.tools.teams.PublicClientApplication", return_value=mock_public_app),
            pytest.raises(Exception, match="invalid_grant"),
        ):
            from openclaw.config import get_config

            acquire_agent_token(get_config())


# ---------------------------------------------------------------------------
# create_or_find_chat
# ---------------------------------------------------------------------------


class TestCreateOrFindChat:
    @respx.mock
    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        respx.post(f"{GRAPH_BASE}/chats").mock(
            return_value=httpx.Response(
                201,
                json={"id": "19:chat-id@thread.v2", "createdDateTime": "2024-01-01"},
            )
        )
        result = await create_or_find_chat(
            token="agent-token",
            human_user_id="human-uid",
        )
        assert result["chat_id"] == "19:chat-id@thread.v2"

    @respx.mock
    @pytest.mark.asyncio
    async def test_expired_token(self) -> None:
        respx.post(f"{GRAPH_BASE}/chats").mock(return_value=httpx.Response(401))
        with pytest.raises(TokenExpiredError):
            await create_or_find_chat(
                token="expired",
                human_user_id="h",
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_teams_not_licensed(self) -> None:
        respx.post(f"{GRAPH_BASE}/chats").mock(return_value=httpx.Response(403))
        with pytest.raises(TeamsNotLicensed):
            await create_or_find_chat(
                token="tok",
                human_user_id="h",
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_rate_limited(self) -> None:
        respx.post(f"{GRAPH_BASE}/chats").mock(
            return_value=httpx.Response(429, headers={"Retry-After": "30"})
        )
        with pytest.raises(RateLimitError) as exc_info:
            await create_or_find_chat(
                token="tok",
                human_user_id="h",
            )
        assert exc_info.value.retry_after == 30


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
        result = await send(chat_id="c1", message="hello!", token="tok")
        assert result["message_id"] == "msg-1"

    @respx.mock
    @pytest.mark.asyncio
    async def test_html_content(self) -> None:
        route = respx.post(f"{GRAPH_BASE}/chats/c1/messages").mock(
            return_value=httpx.Response(201, json={"id": "msg-2", "createdDateTime": "2024-01-01"})
        )
        await send(chat_id="c1", message="<b>hi</b>", token="tok", content_type="html")
        body = route.calls.last.request.content
        assert b"html" in body

    @pytest.mark.asyncio
    async def test_message_too_long(self) -> None:
        long_msg = "x" * (MAX_MESSAGE_LENGTH + 1)
        with pytest.raises(MessageTooLong):
            await send(chat_id="c1", message=long_msg, token="tok")

    @respx.mock
    @pytest.mark.asyncio
    async def test_token_expired(self) -> None:
        respx.post(f"{GRAPH_BASE}/chats/c1/messages").mock(return_value=httpx.Response(401))
        with pytest.raises(TokenExpiredError):
            await send(chat_id="c1", message="hello", token="tok")

    @respx.mock
    @pytest.mark.asyncio
    async def test_rate_limited(self) -> None:
        respx.post(f"{GRAPH_BASE}/chats/c1/messages").mock(
            return_value=httpx.Response(429, headers={"Retry-After": "42"})
        )
        with pytest.raises(RateLimitError) as exc_info:
            await send(chat_id="c1", message="hello", token="tok")
        assert exc_info.value.retry_after == 42

    @respx.mock
    @pytest.mark.asyncio
    async def test_chat_not_found(self) -> None:
        respx.post(f"{GRAPH_BASE}/chats/nope/messages").mock(return_value=httpx.Response(404))
        with pytest.raises(ChatNotFound):
            await send(chat_id="nope", message="hello", token="tok")


# ---------------------------------------------------------------------------
# read
# ---------------------------------------------------------------------------


class TestTeamsRead:
    @respx.mock
    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        respx.get(f"{GRAPH_BASE}/chats/c1/messages").mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "m1",
                            "from": {"user": {"displayName": "Human"}},
                            "body": {"content": "hi agent"},
                            "createdDateTime": "2024-01-01T12:00:00Z",
                        }
                    ]
                },
            )
        )
        result = await read(chat_id="c1", token="tok", count=5)
        assert len(result) == 1
        assert result[0]["message_id"] == "m1"
        assert result[0]["from"] == "Human"
        assert result[0]["content"] == "hi agent"

    @respx.mock
    @pytest.mark.asyncio
    async def test_token_expired(self) -> None:
        respx.get(f"{GRAPH_BASE}/chats/c1/messages").mock(return_value=httpx.Response(401))
        with pytest.raises(TokenExpiredError):
            await read(chat_id="c1", token="expired")

    @respx.mock
    @pytest.mark.asyncio
    async def test_chat_not_found(self) -> None:
        respx.get(f"{GRAPH_BASE}/chats/nope/messages").mock(return_value=httpx.Response(404))
        with pytest.raises(ChatNotFound):
            await read(chat_id="nope", token="tok")

    @respx.mock
    @pytest.mark.asyncio
    async def test_empty_messages(self) -> None:
        respx.get(f"{GRAPH_BASE}/chats/c1/messages").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        result = await read(chat_id="c1", token="tok")
        assert result == []

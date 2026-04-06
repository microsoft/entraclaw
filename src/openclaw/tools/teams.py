"""Teams Graph API integration — 1:1 chat creation and messaging.

All HTTP calls use ``httpx.AsyncClient`` with proper auth headers.
Errors are mapped to the typed hierarchy in ``openclaw.errors``.
"""

from __future__ import annotations

import logging

import httpx

from openclaw.errors import (
    ChatNotFound,
    MessageTooLong,
    RateLimitError,
    TeamsNotLicensed,
    TokenExpiredError,
)
from openclaw.platform import get_credential_store

logger = logging.getLogger("openclaw.tools.teams")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

MAX_MESSAGE_LENGTH = 28_000


def _get_cached_token() -> str:
    """Retrieve the cached OBO token for the active agent."""
    store = get_credential_store()
    client_id = store.retrieve("openclaw", "active_client_id")
    if not client_id:
        raise TokenExpiredError("No active agent identity — run openclaw_bootstrap first")
    token = store.retrieve("openclaw", f"{client_id}/obo_token")
    if not token:
        raise TokenExpiredError("OBO token not found — run openclaw_bootstrap")
    return token


async def connect(human_user_email: str) -> dict:
    """Create or resume a 1:1 Teams chat between the agent and *human_user_email*.

    The Graph ``POST /chats`` call is idempotent for ``oneOnOne`` chats — if
    a chat already exists between the two members it is returned unchanged.
    """
    token = _get_cached_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        # Resolve the agent's own user id
        me_resp = await client.get(f"{GRAPH_BASE}/me", headers=headers)
        if me_resp.status_code == 401:
            raise TokenExpiredError("OBO token expired — re-run openclaw_bootstrap")
        me_resp.raise_for_status()
        agent_user_id = me_resp.json()["id"]

        # Resolve human user by email
        user_resp = await client.get(
            f"{GRAPH_BASE}/users/{human_user_email}",
            headers=headers,
        )
        if user_resp.status_code == 404:
            raise ChatNotFound(f"User {human_user_email} not found in directory")
        user_resp.raise_for_status()
        human_user_id = user_resp.json()["id"]

        # Create (or re-use) 1:1 chat
        chat_payload = {
            "chatType": "oneOnOne",
            "members": [
                {
                    "@odata.type": "#microsoft.graph.aadUserConversationMember",
                    "roles": ["owner"],
                    "user@odata.bind": (
                        f"https://graph.microsoft.com/v1.0/users('{agent_user_id}')"
                    ),
                },
                {
                    "@odata.type": "#microsoft.graph.aadUserConversationMember",
                    "roles": ["owner"],
                    "user@odata.bind": (
                        f"https://graph.microsoft.com/v1.0/users('{human_user_id}')"
                    ),
                },
            ],
        }

        resp = await client.post(
            f"{GRAPH_BASE}/chats",
            json=chat_payload,
            headers=headers,
        )
        if resp.status_code == 403:
            raise TeamsNotLicensed("User does not have a Teams license")
        if resp.status_code == 401:
            raise TokenExpiredError("OBO token expired — re-run openclaw_bootstrap")
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "60"))
            raise RateLimitError(retry_after)
        resp.raise_for_status()

        chat = resp.json()
        logger.info("Teams chat established: %s", chat["id"])
        return {
            "chat_id": chat["id"],
            "created_at": chat.get("createdDateTime"),
        }


async def send(
    chat_id: str,
    message: str,
    content_type: str = "text",
) -> dict:
    """Send *message* to the Teams chat identified by *chat_id*.

    ``content_type`` must be ``"text"`` or ``"html"``.
    """
    if len(message) > MAX_MESSAGE_LENGTH:
        raise MessageTooLong(f"Message is {len(message)} chars, max is {MAX_MESSAGE_LENGTH}")

    token = _get_cached_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GRAPH_BASE}/chats/{chat_id}/messages",
            json={"body": {"contentType": content_type, "content": message}},
            headers=headers,
        )
        if resp.status_code == 401:
            raise TokenExpiredError("OBO token expired — re-run openclaw_bootstrap")
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "60"))
            raise RateLimitError(retry_after)
        if resp.status_code == 404:
            raise ChatNotFound(f"Chat {chat_id} not found")
        resp.raise_for_status()

        msg = resp.json()
        logger.info("Message sent to chat %s: %s", chat_id, msg["id"])
        return {
            "message_id": msg["id"],
            "sent_at": msg.get("createdDateTime"),
        }

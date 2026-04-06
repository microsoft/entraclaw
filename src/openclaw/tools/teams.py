"""Teams Graph API integration — 1:1 chat creation and messaging.

All HTTP calls use ``httpx.AsyncClient`` with proper auth headers.
Errors are mapped to the typed hierarchy in ``openclaw.errors``.

The agent token is acquired via the OBO (On-Behalf-Of) flow:
  1. Retrieve the human's cached refresh token from the OS keychain
  2. Exchange it for a fresh human access token
  3. Perform an OBO exchange: human token → agent-attributed token
Messages are sent attributed to the Agent Identity, not the human.
"""

from __future__ import annotations

import logging

import httpx
from msal import ConfidentialClientApplication, PublicClientApplication

from openclaw.config import OpenclawConfig
from openclaw.errors import (
    AgentIDNotAvailable,
    ChatNotFound,
    MessageTooLong,
    MSALError,
    OBOExchangeError,
    RateLimitError,
    TeamsNotLicensed,
    TokenExpiredError,
)

logger = logging.getLogger("openclaw.tools.teams")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

MAX_MESSAGE_LENGTH = 28_000

# Delegated scopes requested via OBO for the agent
AGENT_SCOPES = [
    "https://graph.microsoft.com/Chat.Create",
    "https://graph.microsoft.com/ChatMessage.Send",
    "https://graph.microsoft.com/Chat.ReadWrite",
    "https://graph.microsoft.com/User.Read",
]


def acquire_agent_token(config: OpenclawConfig) -> str:
    """Acquire an agent-attributed token via the OBO flow.

    Steps:
      1. Retrieve the human's cached refresh token from the OS keychain.
      2. Use a PublicClientApplication to silently get a human access token.
      3. Use a ConfidentialClientApplication to exchange it via OBO.

    The resulting token has ``azp`` = blueprint's client_id (the agent)
    and ``oid`` = the human's object ID, so Entra sign-in logs attribute
    the action to the agent, not the human.

    Raises ``AgentIDNotAvailable`` if config or refresh token is missing,
    ``MSALError`` if the human token acquisition fails,
    or ``OBOExchangeError`` if the OBO exchange fails.
    """
    if not all([config.blueprint_app_id, config.tenant_id, config.blueprint_secret]):
        raise AgentIDNotAvailable(
            "Blueprint credentials not configured. Run ./scripts/setup.sh first."
        )

    from openclaw.platform import get_credential_store

    store = get_credential_store()
    refresh_token = store.retrieve("openclaw", "human_refresh_token")
    if not refresh_token:
        raise AgentIDNotAvailable("No human refresh token found. Run ./scripts/setup.sh first.")

    authority = f"https://login.microsoftonline.com/{config.tenant_id}"

    # Step 1: Acquire a human token using the cached refresh token
    public_app = PublicClientApplication(
        client_id=config.blueprint_app_id,
        authority=authority,
    )

    # Try silent acquisition from MSAL cache first
    accounts = public_app.get_accounts()
    human_result = None
    if accounts:
        human_result = public_app.acquire_token_silent(
            scopes=[f"api://{config.blueprint_app_id}/access_as_user"],
            account=accounts[0],
        )

    if not human_result or "error" in (human_result or {}):
        # Fallback: acquire using the refresh token directly
        # MSAL's acquire_token_by_refresh_token is for migration scenarios
        human_result = public_app.acquire_token_by_refresh_token(
            refresh_token=refresh_token,
            scopes=[f"api://{config.blueprint_app_id}/access_as_user"],
        )

    if not human_result or "error" in human_result:
        error = (human_result or {}).get("error", "unknown_error")
        desc = (human_result or {}).get(
            "error_description",
            "Human token expired. Re-run ./scripts/setup.sh to re-authenticate.",
        )
        raise MSALError(error, desc)

    # Step 2: OBO exchange — human token → agent-attributed token
    confidential_app = ConfidentialClientApplication(
        client_id=config.blueprint_app_id,
        client_credential=config.blueprint_secret,
        authority=authority,
    )

    obo_result = confidential_app.acquire_token_on_behalf_of(
        user_assertion=human_result["access_token"],
        scopes=AGENT_SCOPES,
    )

    if "error" in obo_result:
        raise OBOExchangeError(
            obo_result["error"],
            obo_result.get("error_description", "OBO token exchange failed"),
        )

    return obo_result["access_token"]


async def create_or_find_chat(
    *,
    token: str,
    human_user_id: str,
) -> dict:
    """Create or resume a 1:1 Teams chat with the human.

    With OBO tokens, the agent is identified by the ``azp`` claim in the
    token.  The Graph ``POST /chats`` call is idempotent for ``oneOnOne``
    chats — if a chat already exists it is returned unchanged.

    The ``/me`` reference resolves to the human (whose ``oid`` is in the
    OBO token), and the human_user_id is passed explicitly for the second
    member binding.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    chat_payload = {
        "chatType": "oneOnOne",
        "members": [
            {
                "@odata.type": "#microsoft.graph.aadUserConversationMember",
                "roles": ["owner"],
                "user@odata.bind": "https://graph.microsoft.com/v1.0/me",
            },
            {
                "@odata.type": "#microsoft.graph.aadUserConversationMember",
                "roles": ["owner"],
                "user@odata.bind": (f"https://graph.microsoft.com/v1.0/users('{human_user_id}')"),
            },
        ],
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GRAPH_BASE}/chats",
            json=chat_payload,
            headers=headers,
        )
        if resp.status_code == 403:
            raise TeamsNotLicensed("Agent or human user does not have a Teams license")
        if resp.status_code == 401:
            raise TokenExpiredError("Agent token expired — re-run ./scripts/setup.sh")
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
    *,
    chat_id: str,
    message: str,
    token: str,
    content_type: str = "text",
) -> dict:
    """Send *message* to the Teams chat identified by *chat_id*.

    ``content_type`` must be ``"text"`` or ``"html"``.
    The message is sent FROM the agent user (via the agent's delegated token).
    """
    if len(message) > MAX_MESSAGE_LENGTH:
        raise MessageTooLong(f"Message is {len(message)} chars, max is {MAX_MESSAGE_LENGTH}")

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
            raise TokenExpiredError("Agent token expired — re-run ./scripts/setup.sh")
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


async def read(
    *,
    chat_id: str,
    token: str,
    count: int = 5,
) -> list[dict]:
    """Read recent messages from the human in the Teams chat.

    Returns up to *count* most recent messages, newest first.
    """
    headers = {
        "Authorization": f"Bearer {token}",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GRAPH_BASE}/chats/{chat_id}/messages",
            params={"$top": str(count), "$orderby": "createdDateTime desc"},
            headers=headers,
        )
        if resp.status_code == 401:
            raise TokenExpiredError("Agent token expired — re-run ./scripts/setup.sh")
        if resp.status_code == 404:
            raise ChatNotFound(f"Chat {chat_id} not found")
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "60"))
            raise RateLimitError(retry_after)
        resp.raise_for_status()

        messages = resp.json().get("value", [])
        return [
            {
                "message_id": m["id"],
                "from": m.get("from", {}).get("user", {}).get("displayName", "unknown"),
                "content": m.get("body", {}).get("content", ""),
                "sent_at": m.get("createdDateTime"),
            }
            for m in messages
        ]

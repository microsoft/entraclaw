"""Openclaw MCP server — pre-authenticated Agent User tools.

Authentication is fully automatic. The server loads credentials from .env
(written by scripts/setup.sh), acquires an Agent User token via the three-hop
flow on first tool call, and establishes a Teams chat. The calling LLM does
NOT need to provide any credentials, tokens, or configuration — just call
the tools directly.
"""

from __future__ import annotations

import json
import logging
import sys

from mcp.server.fastmcp import FastMCP

from openclaw.config import get_config
from openclaw.errors import OpenclawError, TokenExchangeError
from openclaw.logging_config import setup_logging

logger: logging.Logger | None = None

mcp = FastMCP(
    "Openclaw Agent Identity",
    instructions=(
        "Openclaw gives you a real Microsoft Entra Agent Identity with its own "
        "Teams presence. Authentication is AUTOMATIC — you do NOT need credentials, "
        "tokens, .env files, or any setup. Just call the tools directly.\n\n"
        "Available tools:\n"
        "- openclaw_whoami: Check your agent identity and Teams connection status\n"
        "- openclaw_teams_send: Send a Teams message to the human user\n"
        "- openclaw_teams_read: Read recent Teams messages from the human\n"
        "- openclaw_audit_log: Record an audit event before taking an action\n\n"
        "Start by calling openclaw_whoami to verify your identity is active."
    ),
)

# Module-level state populated by _initialize()
_state: dict[str, object] = {}


async def _initialize() -> None:
    """Acquire the Agent User token and set up the Teams chat.

    Called lazily on the first tool invocation. All config comes from
    environment variables (loaded from .env by openclaw.config).
    """
    if _state.get("initialized"):
        return

    from openclaw.tools.teams import acquire_agent_user_token, create_or_find_chat

    config = get_config()

    if not config.blueprint_app_id or not config.tenant_id:
        print(  # noqa: T201
            "ERROR: OPENCLAW_BLUEPRINT_APP_ID / OPENCLAW_TENANT_ID not set. "
            "Run ./scripts/setup.sh first.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Acquire Agent User token via three-hop flow
    try:
        token = acquire_agent_user_token(config)
    except (TokenExchangeError, OpenclawError) as exc:
        print(  # noqa: T201
            f"ERROR: Failed to acquire Agent User token. Run ./scripts/setup.sh first.\n{exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    _state["token"] = token
    _state["config"] = config

    # Create / find the Teams chat (requires human user ID)
    if config.human_user_id:
        try:
            chat = await create_or_find_chat(
                token=token,
                human_user_id=config.human_user_id,
            )
            _state["chat_id"] = chat["chat_id"]
        except OpenclawError as exc:
            # Non-fatal: Teams chat is optional (audit still works)
            if logger:
                logger.warning("Could not set up Teams chat: %s", exc)
    else:
        if logger:
            logger.warning("OPENCLAW_HUMAN_USER_ID not set — Teams tools will not work")

    _state["initialized"] = True


@mcp.tool()
async def openclaw_teams_send(message: str, content_type: str = "text") -> str:
    """Send a message to the human user in Microsoft Teams. Authentication is
    automatic — just provide the message text and call this tool. No credentials
    or setup needed from the caller.

    The message is sent FROM the Openclaw Agent User identity (a real Teams
    user), not the human. The human will see it as a message from "Openclaw Agent"
    in their Teams chat.

    Args:
        message: The text to send.
        content_type: "text" (default) or "html" for rich formatting.

    Returns:
        JSON with message_id and sent_at timestamp.
    """
    await _initialize()
    from openclaw.tools.teams import send

    chat_id = _state.get("chat_id")
    if not chat_id:
        return json.dumps({"error": "Teams chat not established. Check setup."})

    token = _state.get("token")
    if not token:
        return json.dumps({"error": "No agent token. Run ./scripts/setup.sh first."})

    result = await send(
        chat_id=str(chat_id),
        message=message,
        token=str(token),
        content_type=content_type,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
async def openclaw_teams_read(count: int = 5) -> str:
    """Read recent messages from the human in the Teams chat. Authentication is
    automatic — just call this tool. No credentials or setup needed from the caller.

    Returns the most recent messages in the 1:1 chat between the Openclaw Agent
    User and the human, newest first.

    Args:
        count: Number of messages to return (default 5, max ~50).

    Returns:
        JSON array of messages, each with message_id, from, content, sent_at.
    """
    await _initialize()
    from openclaw.tools.teams import read

    chat_id = _state.get("chat_id")
    if not chat_id:
        return json.dumps({"error": "Teams chat not established. Check setup."})

    token = _state.get("token")
    if not token:
        return json.dumps({"error": "No agent token. Run ./scripts/setup.sh first."})

    result = await read(
        chat_id=str(chat_id),
        token=str(token),
        count=count,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def openclaw_audit_log(
    action: str,
    resource: str,
    outcome: str = "success",
    metadata: str = "{}",
) -> str:
    """Record an audit event. Call this BEFORE performing any action on the
    user's behalf. No credentials needed — works immediately.

    The audit trail proves the agent (not the human) performed the action.
    Events are written to ~/.openclaw/audit/ as daily JSONL files.

    Args:
        action: What the agent is doing (e.g., "file_read", "code_execute").
        resource: What is being acted on (e.g., file path, URL, repo name).
        outcome: "success", "failure", or "pending" (default "success").
        metadata: Optional JSON string of key-value pairs with extra context.

    Returns:
        JSON with event_id, timestamp, and the recorded event.
    """
    from openclaw.tools.audit import log_event

    config = get_config()
    meta = json.loads(metadata) if metadata else {}
    result = log_event(
        action=action,
        resource=resource,
        outcome=outcome,
        agent_id=config.agent_id or config.blueprint_app_id or "unknown",
        metadata=meta,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
async def openclaw_whoami() -> str:
    """Show the current agent identity, Teams connection status, and permissions.
    Call this first to verify the agent is authenticated and connected.

    Authentication is automatic — no credentials needed. Returns the agent's
    identity details including tenant, blueprint, agent ID, and whether the
    Teams chat is active.

    Returns:
        JSON with agent identity details and connection status.
    """
    await _initialize()
    from openclaw.tools.identity import whoami

    token = _state.get("token")
    result = await whoami(token=str(token) if token else None)
    result["teams_chat_id"] = _state.get("chat_id", "not_connected")
    return json.dumps(result, indent=2)


def main() -> None:
    """Entry point for ``openclaw-mcp`` console script."""
    global logger
    logger = setup_logging()
    logger.info("Starting Openclaw MCP server (Agent User auth)")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

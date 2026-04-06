"""Openclaw MCP server — wires tools to the FastMCP transport.

Run directly with ``python -m openclaw.mcp_server`` or via the
``openclaw-mcp`` console script.  The server communicates over stdio
so Copilot CLI can connect as a regular MCP client.
"""

from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import FastMCP

from openclaw.logging_config import setup_logging

logger: logging.Logger | None = None

mcp = FastMCP("Openclaw Agent Identity")


@mcp.tool()
async def openclaw_bootstrap(tenant_id: str = "") -> str:
    """Bootstrap agent identity: human signs in, app registration is created, OBO token is acquired.

    This is the first tool to call. It runs two device-code flows:
    1. Sign in with Azure CLI app to get admin Graph access
    2. Re-authenticate with the newly created app for OBO exchange

    Returns JSON with agent_id, tenant_id, device_code_message, and second_auth_message.
    """
    from openclaw.tools.identity import bootstrap

    result = await bootstrap(tenant_id=tenant_id or None)
    return json.dumps(result, indent=2)


@mcp.tool()
async def openclaw_teams_connect(human_user_email: str) -> str:
    """Create or resume a 1:1 Teams chat between the agent and the specified human user.

    The chat is idempotent — calling this again with the same email returns the existing chat.
    Requires a valid OBO token (run openclaw_bootstrap first).
    """
    from openclaw.tools.teams import connect

    result = await connect(human_user_email=human_user_email)
    return json.dumps(result, indent=2)


@mcp.tool()
async def openclaw_teams_send(
    chat_id: str,
    message: str,
    content_type: str = "text",
) -> str:
    """Send a message to the human in a Teams chat.

    content_type can be 'text' (default) or 'html'.
    Maximum message length is 28,000 characters.
    """
    from openclaw.tools.teams import send

    result = await send(chat_id=chat_id, message=message, content_type=content_type)
    return json.dumps(result, indent=2)


@mcp.tool()
def openclaw_audit_log(
    action: str,
    resource: str,
    outcome: str = "success",
    metadata: str = "{}",
) -> str:
    """Record an audit event for agent action tracking.

    metadata should be a JSON string of key-value pairs.
    Events are written to ~/.openclaw/audit/ as daily JSONL files.
    """
    from openclaw.tools.audit import log_event

    meta = json.loads(metadata) if metadata else {}
    result = log_event(action=action, resource=resource, outcome=outcome, metadata=meta)
    return json.dumps(result, indent=2)


def main() -> None:
    """Entry point for ``openclaw-mcp`` console script."""
    global logger
    logger = setup_logging()
    logger.info("Starting Openclaw MCP server")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

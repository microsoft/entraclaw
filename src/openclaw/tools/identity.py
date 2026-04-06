"""Self-bootstrapping identity flow for Openclaw agents.

Two device-code flows:
1. Azure CLI app → admin Graph token to create the Entra app registration
2. Newly-created app → user token with custom scope for OBO exchange

All MSAL results are checked for the ``error`` key before accessing tokens.
"""

from __future__ import annotations

import logging
import uuid

import httpx
from msal import ConfidentialClientApplication, PublicClientApplication

from openclaw.errors import (
    DeviceCodeTimeout,
    MSALError,
    OBOExchangeError,
)
from openclaw.platform import get_credential_store

logger = logging.getLogger("openclaw.tools.identity")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Azure CLI first-party app — used only for the initial admin device-code flow
BOOTSTRAP_CLIENT_ID = "04b07795-a710-4e5e-9ceb-f95e6d3e6e3e"

DEVICE_CODE_TIMEOUT = 120  # seconds


def _check_msal_result(result: dict, timeout_message: str = "") -> None:
    """Raise the appropriate error if *result* contains an error key."""
    if "error" not in result:
        return
    error = result["error"]
    desc = result.get("error_description", "")
    if error == "authorization_pending":
        raise DeviceCodeTimeout(timeout_message or "Device code flow timed out")
    raise MSALError(error, desc)


async def _get_or_create_app_registration(
    human_token: str,
) -> tuple[str, str]:
    """Return ``(app_id, object_id)`` for the Openclaw Agent app registration.

    Creates the registration if it doesn't exist yet.
    """
    headers = {"Authorization": f"Bearer {human_token}"}
    async with httpx.AsyncClient() as client:
        # Check for existing registration
        resp = await client.get(
            f"{GRAPH_BASE}/applications",
            params={"$filter": "displayName eq 'Openclaw Agent'"},
            headers=headers,
        )
        resp.raise_for_status()
        apps = resp.json().get("value", [])
        if apps:
            return apps[0]["appId"], apps[0]["id"]

        # Build new registration payload
        scope_id = str(uuid.uuid4())
        payload = {
            "displayName": "Openclaw Agent",
            "signInAudience": "AzureADMyOrg",
            "requiredResourceAccess": [
                {
                    "resourceAppId": "00000003-0000-0000-c000-000000000000",
                    "resourceAccess": [
                        # User.Read
                        {"id": "e1fe6dd8-ba31-4d61-89e7-88639da4683d", "type": "Scope"},
                        # Chat.Create
                        {"id": "9ff7295e-131b-4d94-90e1-69fde507ac11", "type": "Scope"},
                        # ChatMessage.Send
                        {"id": "116b7235-7cc6-461e-b163-8e55691d839e", "type": "Scope"},
                        # Chat.ReadWrite
                        {"id": "7427e0e9-2fba-42fe-b0c0-848c9e6a8182", "type": "Scope"},
                    ],
                }
            ],
            "api": {
                "requestedAccessTokenVersion": 2,
                "oauth2PermissionScopes": [
                    {
                        "adminConsentDescription": (
                            "Allow Openclaw agent to act on behalf of the user"
                        ),
                        "adminConsentDisplayName": "Access as user",
                        "id": scope_id,
                        "isEnabled": True,
                        "type": "User",
                        "userConsentDescription": ("Allow Openclaw agent to act on your behalf"),
                        "userConsentDisplayName": "Access as user",
                        "value": "access_as_user",
                    }
                ],
            },
        }

        resp = await client.post(
            f"{GRAPH_BASE}/applications",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        app_reg = resp.json()
        return app_reg["appId"], app_reg["id"]


async def _ensure_client_secret(
    human_token: str,
    client_id: str,
    object_id: str,
) -> str:
    """Return a client secret, creating one if we don't have a cached copy."""
    store = get_credential_store()
    cached = store.retrieve("openclaw", f"{client_id}/client_secret")
    if cached:
        return cached

    headers = {"Authorization": f"Bearer {human_token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GRAPH_BASE}/applications/{object_id}/addPassword",
            json={"passwordCredential": {"displayName": "Openclaw MCP Server"}},
            headers=headers,
        )
        resp.raise_for_status()
        secret = resp.json()["secretText"]

    store.store("openclaw", f"{client_id}/client_secret", secret)
    return secret


async def _ensure_service_principal(
    human_token: str,
    client_id: str,
) -> None:
    """Create a service principal for the app if one doesn't exist."""
    headers = {"Authorization": f"Bearer {human_token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GRAPH_BASE}/servicePrincipals",
            params={"$filter": f"appId eq '{client_id}'"},
            headers=headers,
        )
        resp.raise_for_status()
        if resp.json().get("value"):
            return

        resp = await client.post(
            f"{GRAPH_BASE}/servicePrincipals",
            json={"appId": client_id},
            headers=headers,
        )
        resp.raise_for_status()


async def bootstrap(tenant_id: str | None = None) -> dict:
    """Run the full self-bootstrapping identity flow.

    Returns a dict with agent identity details and auth messages.
    """
    # --- Phase 1: human signs in via Azure CLI app ---
    authority = f"https://login.microsoftonline.com/{tenant_id or 'organizations'}"
    public_app = PublicClientApplication(BOOTSTRAP_CLIENT_ID, authority=authority)

    flow = public_app.initiate_device_flow(
        scopes=["https://graph.microsoft.com/.default"],
    )
    if "error" in flow:
        raise MSALError(flow["error"], flow.get("error_description", ""))

    device_code_message = (
        f"To sign in, visit {flow['verification_uri']} and enter code {flow['user_code']}"
    )
    logger.info("Waiting for human sign-in via device code flow")

    result = public_app.acquire_token_by_device_flow(flow, timeout=DEVICE_CODE_TIMEOUT)
    _check_msal_result(result, "Device code flow timed out after 2 minutes")

    human_token: str = result["access_token"]

    # Discover tenant from token claims
    if not tenant_id:
        claims = result.get("id_token_claims", {})
        tenant_id = claims.get("tid", "unknown")

    # --- Phase 2: create / find app registration ---
    client_id, object_id = await _get_or_create_app_registration(human_token)

    # --- Phase 3: ensure client secret ---
    client_secret = await _ensure_client_secret(human_token, client_id, object_id)

    # --- Phase 4: ensure service principal ---
    await _ensure_service_principal(human_token, client_id)

    # --- Phase 5: second device-code flow with our own app ---
    custom_scope = f"api://{client_id}/access_as_user"
    our_authority = f"https://login.microsoftonline.com/{tenant_id}"
    our_app = PublicClientApplication(client_id, authority=our_authority)

    flow2 = our_app.initiate_device_flow(scopes=[custom_scope])
    if "error" in flow2:
        raise MSALError(flow2["error"], flow2.get("error_description", ""))

    second_auth_message = (
        f"Re-authenticate for agent identity: visit {flow2['verification_uri']} "
        f"and enter code {flow2['user_code']}"
    )
    logger.info("Waiting for human re-auth with custom scope for OBO")

    result2 = our_app.acquire_token_by_device_flow(flow2, timeout=DEVICE_CODE_TIMEOUT)
    _check_msal_result(result2, "Second device code flow timed out")

    # --- Phase 6: OBO exchange ---
    confidential_app = ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=our_authority,
    )

    obo_result = confidential_app.acquire_token_on_behalf_of(
        user_assertion=result2["access_token"],
        scopes=[
            "https://graph.microsoft.com/Chat.Create",
            "https://graph.microsoft.com/ChatMessage.Send",
            "https://graph.microsoft.com/Chat.ReadWrite",
            "https://graph.microsoft.com/User.Read",
        ],
    )
    if "error" in obo_result:
        raise OBOExchangeError(
            obo_result["error"],
            obo_result.get("error_description", ""),
        )

    # --- Phase 7: cache OBO token ---
    store = get_credential_store()
    store.store("openclaw", f"{client_id}/obo_token", obo_result["access_token"])
    store.store("openclaw", "active_client_id", client_id)
    store.store("openclaw", "tenant_id", tenant_id)

    logger.info("Bootstrap complete — agent identity %s ready", client_id)
    return {
        "agent_id": client_id,
        "tenant_id": tenant_id,
        "client_id": client_id,
        "object_id": object_id,
        "scopes": obo_result.get("scope", ""),
        "expires_in": obo_result.get("expires_in", 3600),
        "device_code_message": device_code_message,
        "second_auth_message": second_auth_message,
    }

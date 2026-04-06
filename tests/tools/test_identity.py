"""Tests for the identity bootstrap flow.

MSAL and httpx are fully mocked — no real auth or network calls are made.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from openclaw.errors import DeviceCodeTimeout, MSALError, OBOExchangeError
from openclaw.tools.identity import (
    BOOTSTRAP_CLIENT_ID,
    GRAPH_BASE,
    _check_msal_result,
    _ensure_client_secret,
    _ensure_service_principal,
    _get_or_create_app_registration,
    bootstrap,
)

# ---------------------------------------------------------------------------
# Unit: _check_msal_result
# ---------------------------------------------------------------------------


class TestCheckMSALResult:
    def test_no_error_is_noop(self) -> None:
        _check_msal_result({"access_token": "tok"})

    def test_authorization_pending_raises_timeout(self) -> None:
        with pytest.raises(DeviceCodeTimeout):
            _check_msal_result({"error": "authorization_pending"})

    def test_generic_error_raises_msal_error(self) -> None:
        with pytest.raises(MSALError) as exc_info:
            _check_msal_result({"error": "invalid_grant", "error_description": "bad token"})
        assert exc_info.value.error == "invalid_grant"


# ---------------------------------------------------------------------------
# Unit: _get_or_create_app_registration
# ---------------------------------------------------------------------------


class TestGetOrCreateAppRegistration:
    @respx.mock
    @pytest.mark.asyncio
    async def test_existing_app_returned(self) -> None:
        respx.get(f"{GRAPH_BASE}/applications").mock(
            return_value=httpx.Response(
                200,
                json={"value": [{"appId": "existing-id", "id": "obj-id"}]},
            )
        )
        app_id, obj_id = await _get_or_create_app_registration("fake-token")
        assert app_id == "existing-id"
        assert obj_id == "obj-id"

    @respx.mock
    @pytest.mark.asyncio
    async def test_new_app_created(self) -> None:
        respx.get(f"{GRAPH_BASE}/applications").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.post(f"{GRAPH_BASE}/applications").mock(
            return_value=httpx.Response(
                201,
                json={"appId": "new-id", "id": "new-obj-id"},
            )
        )
        app_id, obj_id = await _get_or_create_app_registration("fake-token")
        assert app_id == "new-id"
        assert obj_id == "new-obj-id"


# ---------------------------------------------------------------------------
# Unit: _ensure_client_secret
# ---------------------------------------------------------------------------


class TestEnsureClientSecret:
    @respx.mock
    @pytest.mark.asyncio
    async def test_cached_secret_returned(self) -> None:
        mock_store = MagicMock()
        mock_store.retrieve.return_value = "cached-secret"
        with patch("openclaw.tools.identity.get_credential_store", return_value=mock_store):
            secret = await _ensure_client_secret("tok", "cid", "oid")
        assert secret == "cached-secret"

    @respx.mock
    @pytest.mark.asyncio
    async def test_new_secret_created_and_cached(self) -> None:
        mock_store = MagicMock()
        mock_store.retrieve.return_value = None
        respx.post(f"{GRAPH_BASE}/applications/oid/addPassword").mock(
            return_value=httpx.Response(200, json={"secretText": "new-secret"})
        )
        with patch("openclaw.tools.identity.get_credential_store", return_value=mock_store):
            secret = await _ensure_client_secret("tok", "cid", "oid")
        assert secret == "new-secret"
        mock_store.store.assert_called_once_with("openclaw", "cid/client_secret", "new-secret")


# ---------------------------------------------------------------------------
# Unit: _ensure_service_principal
# ---------------------------------------------------------------------------


class TestEnsureServicePrincipal:
    @respx.mock
    @pytest.mark.asyncio
    async def test_existing_sp_noop(self) -> None:
        respx.get(f"{GRAPH_BASE}/servicePrincipals").mock(
            return_value=httpx.Response(200, json={"value": [{"id": "sp1"}]})
        )
        await _ensure_service_principal("tok", "cid")

    @respx.mock
    @pytest.mark.asyncio
    async def test_creates_sp_when_missing(self) -> None:
        respx.get(f"{GRAPH_BASE}/servicePrincipals").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        route = respx.post(f"{GRAPH_BASE}/servicePrincipals").mock(
            return_value=httpx.Response(201, json={"id": "new-sp"})
        )
        await _ensure_service_principal("tok", "cid")
        assert route.called


# ---------------------------------------------------------------------------
# Integration: full bootstrap (all external calls mocked)
# ---------------------------------------------------------------------------


class TestBootstrapFull:
    @respx.mock
    @pytest.mark.asyncio
    async def test_bootstrap_happy_path(self) -> None:
        """Full bootstrap with both device-code flows and OBO succeeding."""
        # Mock MSAL
        mock_public_app = MagicMock()
        mock_public_app.initiate_device_flow.return_value = {
            "verification_uri": "https://aka.ms/devicelogin",
            "user_code": "ABCDEF",
        }
        mock_public_app.acquire_token_by_device_flow.return_value = {
            "access_token": "human-token",
            "id_token_claims": {"tid": "test-tenant"},
        }

        mock_our_app = MagicMock()
        mock_our_app.initiate_device_flow.return_value = {
            "verification_uri": "https://aka.ms/devicelogin",
            "user_code": "GHIJKL",
        }
        mock_our_app.acquire_token_by_device_flow.return_value = {
            "access_token": "user-token-for-obo",
        }

        mock_conf_app = MagicMock()
        mock_conf_app.acquire_token_on_behalf_of.return_value = {
            "access_token": "obo-token",
            "scope": "Chat.Create ChatMessage.Send",
            "expires_in": 3600,
        }

        # Track which class gets which args
        public_app_calls: list[tuple] = []

        def mock_public_init(client_id, authority):
            public_app_calls.append((client_id, authority))
            if client_id == BOOTSTRAP_CLIENT_ID:
                return mock_public_app
            return mock_our_app

        # Mock Graph API
        respx.get(f"{GRAPH_BASE}/applications").mock(
            return_value=httpx.Response(
                200,
                json={"value": [{"appId": "agent-cid", "id": "agent-oid"}]},
            )
        )
        respx.get(f"{GRAPH_BASE}/servicePrincipals").mock(
            return_value=httpx.Response(200, json={"value": [{"id": "sp"}]})
        )

        mock_store = MagicMock()
        mock_store.retrieve.return_value = "cached-secret"

        with (
            patch("openclaw.tools.identity.PublicClientApplication", side_effect=mock_public_init),
            patch(
                "openclaw.tools.identity.ConfidentialClientApplication",
                return_value=mock_conf_app,
            ),
            patch("openclaw.tools.identity.get_credential_store", return_value=mock_store),
        ):
            result = await bootstrap()

        assert result["agent_id"] == "agent-cid"
        assert result["tenant_id"] == "test-tenant"
        assert "ABCDEF" in result["device_code_message"]
        assert "GHIJKL" in result["second_auth_message"]

    @pytest.mark.asyncio
    async def test_bootstrap_device_flow_error(self) -> None:
        """initiate_device_flow returning an error raises MSALError."""
        mock_app = MagicMock()
        mock_app.initiate_device_flow.return_value = {
            "error": "invalid_client",
            "error_description": "Client not found",
        }
        with (
            patch("openclaw.tools.identity.PublicClientApplication", return_value=mock_app),
            pytest.raises(MSALError, match="invalid_client"),
        ):
            await bootstrap()

    @respx.mock
    @pytest.mark.asyncio
    async def test_bootstrap_obo_failure(self) -> None:
        """OBO exchange error is raised as OBOExchangeError."""
        mock_public = MagicMock()
        mock_public.initiate_device_flow.return_value = {
            "verification_uri": "https://aka.ms/devicelogin",
            "user_code": "CODE",
        }
        mock_public.acquire_token_by_device_flow.return_value = {
            "access_token": "tok",
            "id_token_claims": {"tid": "t"},
        }

        mock_conf = MagicMock()
        mock_conf.acquire_token_on_behalf_of.return_value = {
            "error": "interaction_required",
            "error_description": "Consent needed",
        }

        respx.get(f"{GRAPH_BASE}/applications").mock(
            return_value=httpx.Response(200, json={"value": [{"appId": "cid", "id": "oid"}]})
        )
        respx.get(f"{GRAPH_BASE}/servicePrincipals").mock(
            return_value=httpx.Response(200, json={"value": [{"id": "sp"}]})
        )

        mock_store = MagicMock()
        mock_store.retrieve.return_value = "secret"

        with (
            patch(
                "openclaw.tools.identity.PublicClientApplication",
                return_value=mock_public,
            ),
            patch(
                "openclaw.tools.identity.ConfidentialClientApplication",
                return_value=mock_conf,
            ),
            patch("openclaw.tools.identity.get_credential_store", return_value=mock_store),
            pytest.raises(OBOExchangeError),
        ):
            await bootstrap()

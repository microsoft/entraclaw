"""Tests for the Openclaw error hierarchy."""

import pytest

from openclaw.errors import (
    AgentIDNotAvailable,
    AuthError,
    ChatNotFound,
    ConsentDenied,
    DeviceCodeTimeout,
    MessageTooLong,
    MSALError,
    OBOExchangeError,
    OpenclawError,
    RateLimitError,
    TeamsError,
    TeamsNotLicensed,
    TokenExpiredError,
)


class TestErrorHierarchy:
    """Verify that error classes inherit from the expected bases."""

    def test_auth_errors_inherit_openclaw(self) -> None:
        assert issubclass(AuthError, OpenclawError)

    def test_msal_error_inherits_auth(self) -> None:
        assert issubclass(MSALError, AuthError)

    def test_device_code_timeout_inherits_auth(self) -> None:
        assert issubclass(DeviceCodeTimeout, AuthError)

    def test_consent_denied_inherits_auth(self) -> None:
        assert issubclass(ConsentDenied, AuthError)

    def test_obo_exchange_error_inherits_auth(self) -> None:
        assert issubclass(OBOExchangeError, AuthError)

    def test_agent_id_not_available_inherits_auth(self) -> None:
        assert issubclass(AgentIDNotAvailable, AuthError)

    def test_token_expired_inherits_auth(self) -> None:
        assert issubclass(TokenExpiredError, AuthError)

    def test_teams_errors_inherit_openclaw(self) -> None:
        assert issubclass(TeamsError, OpenclawError)

    def test_teams_not_licensed_inherits_teams(self) -> None:
        assert issubclass(TeamsNotLicensed, TeamsError)

    def test_chat_not_found_inherits_teams(self) -> None:
        assert issubclass(ChatNotFound, TeamsError)

    def test_message_too_long_inherits_teams(self) -> None:
        assert issubclass(MessageTooLong, TeamsError)

    def test_rate_limit_inherits_openclaw(self) -> None:
        assert issubclass(RateLimitError, OpenclawError)


class TestErrorMessages:
    def test_msal_error_message(self) -> None:
        err = MSALError("invalid_grant", "Token expired")
        assert "invalid_grant" in str(err)
        assert "Token expired" in str(err)
        assert err.error == "invalid_grant"
        assert err.description == "Token expired"

    def test_obo_exchange_error_message(self) -> None:
        err = OBOExchangeError("interaction_required", "Consent needed")
        assert "interaction_required" in str(err)
        assert err.error == "interaction_required"

    def test_rate_limit_retry_after(self) -> None:
        err = RateLimitError(30)
        assert err.retry_after == 30
        assert "30" in str(err)

    def test_rate_limit_default_retry(self) -> None:
        err = RateLimitError()
        assert err.retry_after == 60

    def test_catch_all_openclaw_errors(self) -> None:
        """All custom errors can be caught with ``except OpenclawError``."""
        errors = [
            MSALError("e", "d"),
            DeviceCodeTimeout("t"),
            ConsentDenied("c"),
            OBOExchangeError("e", "d"),
            AgentIDNotAvailable("a"),
            TokenExpiredError("t"),
            TeamsNotLicensed("l"),
            ChatNotFound("c"),
            MessageTooLong("m"),
            RateLimitError(10),
        ]
        for err in errors:
            with pytest.raises(OpenclawError):
                raise err

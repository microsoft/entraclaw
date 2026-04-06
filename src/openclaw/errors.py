"""Openclaw error hierarchy.

All Openclaw errors inherit from OpenclawError so callers can catch broadly
or narrow down to specific failure modes.
"""


class OpenclawError(Exception):
    """Base class for all Openclaw errors."""


class AuthError(OpenclawError):
    """Authentication/identity errors."""


class MSALError(AuthError):
    """MSAL returned an error dict instead of a token."""

    def __init__(self, error: str, description: str) -> None:
        self.error = error
        self.description = description
        super().__init__(f"{error}: {description}")


class DeviceCodeTimeout(AuthError):
    """Device code flow timed out waiting for user authentication."""


class ConsentDenied(AuthError):
    """User denied consent for requested permissions."""


class OBOExchangeError(AuthError):
    """On-behalf-of token exchange failed."""

    def __init__(self, error: str, description: str) -> None:
        self.error = error
        self.description = description
        super().__init__(f"OBO exchange failed — {error}: {description}")


class AgentIDNotAvailable(AuthError):
    """Agent identity has not been bootstrapped yet."""


class TokenExpiredError(AuthError):
    """Cached token has expired and needs refresh."""


class TeamsError(OpenclawError):
    """Teams Graph API errors."""


class TeamsNotLicensed(TeamsError):
    """User does not have a Teams license."""


class ChatNotFound(TeamsError):
    """Referenced chat does not exist or is inaccessible."""


class MessageTooLong(TeamsError):
    """Message exceeds the Teams character limit."""


class RateLimitError(OpenclawError):
    """Graph API returned 429 — too many requests."""

    def __init__(self, retry_after: int = 60) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limited. Retry after {retry_after}s")

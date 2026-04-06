"""Environment-based configuration for Openclaw.

Uses a simple dataclass with fallback defaults. Values are read from
environment variables prefixed with OPENCLAW_.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _default_dir(subdir: str) -> Path:
    return Path.home() / ".openclaw" / subdir


@dataclass(frozen=True)
class OpenclawConfig:
    """Immutable configuration loaded from environment variables."""

    tenant_id: str | None = field(default=None)
    client_id: str | None = field(default=None)
    client_secret: str | None = field(default=None)
    log_dir: Path = field(default_factory=lambda: _default_dir("logs"))
    audit_dir: Path = field(default_factory=lambda: _default_dir("audit"))
    data_dir: Path = field(default_factory=lambda: _default_dir("data"))
    log_level: str = field(default="INFO")

    @classmethod
    def from_env(cls) -> OpenclawConfig:
        """Build config from OPENCLAW_* environment variables."""
        return cls(
            tenant_id=os.environ.get("OPENCLAW_TENANT_ID"),
            client_id=os.environ.get("OPENCLAW_CLIENT_ID"),
            client_secret=os.environ.get("OPENCLAW_CLIENT_SECRET"),
            log_dir=Path(os.environ.get("OPENCLAW_LOG_DIR", _default_dir("logs"))),
            audit_dir=Path(os.environ.get("OPENCLAW_AUDIT_DIR", _default_dir("audit"))),
            data_dir=Path(os.environ.get("OPENCLAW_DATA_DIR", _default_dir("data"))),
            log_level=os.environ.get("OPENCLAW_LOG_LEVEL", "INFO"),
        )


def get_config() -> OpenclawConfig:
    """Convenience accessor — returns config from current environment."""
    return OpenclawConfig.from_env()

"""Regression tests for suite-level environment isolation."""

from __future__ import annotations

import os


def test_blob_storage_env_is_cleared_by_default() -> None:
    """Parent shell blob settings must not leak into local-storage tests."""
    assert "ENTRACLAW_BLOB_ENDPOINT" not in os.environ
    assert "ENTRACLAW_BLOB_CONTAINER" not in os.environ
    assert "ENTRACLAW_KEEP_MEMORY_LOCAL" not in os.environ

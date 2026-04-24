"""Shared pytest fixtures for the entraclaw test suite."""

from __future__ import annotations

import logging

import pytest


@pytest.fixture(autouse=True)
def _attach_caplog_to_entraclaw(caplog: pytest.LogCaptureFixture) -> None:
    """Let pytest's caplog capture records from the entraclaw logger.

    ``entraclaw.logging_config.setup_logging`` sets ``propagate = False`` on the
    ``entraclaw`` logger so records don't surface through FastMCP's rich handler
    on root (which doubles stderr volume). caplog's handler is attached to root
    by default, so with propagation blocked it would never see entraclaw
    records. Attaching caplog's handler directly to the entraclaw logger for
    the duration of each test restores the expected capture behavior without
    re-enabling production propagation.
    """
    entraclaw_logger = logging.getLogger("entraclaw")
    entraclaw_logger.addHandler(caplog.handler)
    try:
        yield
    finally:
        entraclaw_logger.removeHandler(caplog.handler)

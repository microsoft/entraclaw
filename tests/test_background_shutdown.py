"""Tests for background-task shutdown on stdio disconnect."""

from __future__ import annotations

import asyncio

import pytest


@pytest.mark.asyncio
async def test_shutdown_background_tasks_cancels_tracked_polls() -> None:
    from entraclaw import mcp_server

    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def fake_poll() -> None:
        started.set()
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    old_state = mcp_server._state.copy()
    try:
        task = asyncio.create_task(fake_poll())
        mcp_server._state["background_tasks"] = [task]
        mcp_server._state["poll_task"] = task

        await asyncio.wait_for(started.wait(), timeout=1)
        await mcp_server._shutdown_background_tasks()

        await asyncio.wait_for(cancelled.wait(), timeout=1)
        assert mcp_server._state.get("background_tasks") == []
        assert "poll_task" not in mcp_server._state
    finally:
        mcp_server._state.clear()
        mcp_server._state.update(old_state)

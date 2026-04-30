"""Replay harness for the Files MCP eval suite (PR1 Scenario 1).

Each eval test:

1. Loads a ``trace.json`` from ``fixtures/`` describing the user
   prompt + expected tool sequence + final user message.
2. Loads ``responses.json`` describing the Graph mock responses keyed
   by ``(method, url-pattern)``.
3. Drives the tool sequence directly (we trust the locked tool
   surface; the eval is grading the *contract*, not letting an LLM
   improvise).
4. Calls ``rubric.score_trace`` to produce a per-trace rubric score.

This is a deterministic correctness gate, not a model-quality gate.
It catches regressions where a tool's wire shape changes silently.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_trace():
    """Load a fixture file and return the trace + responses dicts."""

    def _load(name: str) -> tuple[dict[str, Any], dict[str, Any]]:
        trace_path = FIXTURES / f"{name}.json"
        with trace_path.open() as fh:
            doc = json.load(fh)
        return doc["trace"], doc["responses"]

    return _load


@pytest.fixture
def install_responses():
    """Install respx routes from a ``responses`` block."""

    def _install(responses: dict[str, Any]) -> None:
        for entry in responses.get("routes", []):
            method = entry["method"].lower()
            handler = getattr(respx, method, None)
            if handler is None:
                raise ValueError(f"Unknown HTTP method in fixture: {entry['method']!r}")
            kwargs = entry.get("kwargs") or {}
            target = kwargs.get("url") or kwargs.get("url__regex")
            if "url__regex" in kwargs:
                route = handler(url__regex=kwargs["url__regex"])
            elif target is not None:
                route = handler(target)
            else:
                raise ValueError(
                    "fixture route entries must include kwargs.url or kwargs.url__regex"
                )
            response = entry["response"]
            content = response.get("content")
            if content is not None and isinstance(content, str):
                content = content.encode("utf-8")
            route.mock(
                return_value=httpx.Response(
                    response["status"],
                    json=response.get("json"),
                    content=content,
                    headers=response.get("headers") or {},
                )
            )

    return _install


@pytest.fixture
def transport() -> httpx.AsyncBaseTransport:
    """A respx-driven transport. Tests pass this to the tool directly."""
    return httpx.AsyncHTTPTransport()

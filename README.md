# openclaw-identity-research

Research project for securing agentic workflows on local devices using Microsoft Entra Agent IDs and on-behalf-of (OBO) token flows.

## Goal

Enable autonomous agents running on Mac/Linux/Windows to:

1. Obtain an **Agent ID** that distinguishes them from the human user
2. Request **OBO tokens** with explicit user consent
3. Have all agent actions **tracked in audit logs** — separate from user actions
4. Connect to **Teams** as an "Agent User" to receive commands

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest
```

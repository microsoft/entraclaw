# openclaw-identity-research

Research project for securing agentic workflows on local devices using Microsoft Entra Agent IDs and on-behalf-of (OBO) token flows. Agents get their own identity so audit logs always distinguish agent actions from human actions.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
pytest -v
```

## Architecture

Four modules handle the agent identity lifecycle on Mac/Linux/Windows:

- **platform/** — OS-specific agent identity (keychain, credential storage, consent UX)
- **auth/** — OBO token exchange with Microsoft Entra, Agent ID registration
- **audit/** — Action tracking — every resource access emits an audit event before executing
- **teams/** — Bidirectional Teams communication (agent ↔ human via Graph API)

## Repository Map

| Directory | Purpose |
|-----------|---------|
| `src/openclaw/` | Application source code |
| `tests/` | Test suite (mirrors `src/` structure) |
| `docs/` | Documentation site (MkDocs Material) |
| `.github/` | CI workflows and Copilot instructions |

## Documentation

```bash
pip install mkdocs-material
mkdocs serve
```

Open http://localhost:8000 — or see the [docs/index.md](docs/index.md) for a reading guide.

# Openclaw Identity Research

Research project for securing agentic workflows on local devices (Mac/Linux/Windows) using Microsoft Entra Agent IDs and Agent Users. Agents get their own identity — a real Entra user account with Teams presence, mailbox, and M365 license — so audit logs always distinguish agent actions from human actions.

## Getting Started

### Prerequisites

- Azure CLI (`az`) logged in with admin access to your Entra tenant
- Python 3.12+
- Git
- An M365 license available for the Agent User (E3/E5/Teams Enterprise)

### One-Command Setup

```bash
./scripts/setup.sh
```

This script will:

1. Create a dedicated provisioner app registration (avoids Azure CLI token rejection)
2. Create an Agent Identity Blueprint + BlueprintPrincipal + Agent Identity
3. Create an Agent User (Entra user account linked to the Agent Identity)
4. Grant consent for Teams/Chat Graph permissions
5. Create a Blueprint client secret and write `.env`

The script is **idempotent** — safe to re-run. State persists in `.openclaw-state.json`.

After setup, **assign an M365 license** (E3/E5/Teams Enterprise) to the Agent User in the Entra admin center and wait 10-15 minutes for Teams provisioning.

### Run the MCP Server

Add Openclaw to your Copilot CLI config:

```jsonc
// ~/.copilot/mcp-config.json
{
  "mcpServers": {
    "openclaw": {
      "command": "python3.12",
      "args": ["-m", "openclaw.mcp_server"],
      "cwd": "/path/to/openclaw-identity-research",
      "env": {}
    }
  }
}
```

Then launch Copilot CLI:

```bash
copilot
```

Available tools:

- `openclaw_whoami` — show agent identity and connection status
- `openclaw_teams_send` — send a message to the human as the Agent User
- `openclaw_teams_read` — read recent messages from the human
- `openclaw_audit_log` — record an audit event

### Without an Entra Tenant

To run the code and tests locally without a tenant:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -v
```

All Graph API calls are mocked in tests.

### Teardown

```bash
./scripts/teardown.sh
```

Removes the Agent User, Agent Identity, Blueprint, Provisioner app, and all local state.

## Architecture

The agent authenticates via the **three-hop Agent User flow** — fully autonomous, no human in the loop:

```
Blueprint (client_credentials)
  → Agent Identity (FIC exchange)
    → Agent User (user_fic grant, idtyp=user)
      → Graph API: Teams, Mail, OneDrive
```

Four modules handle the agent identity lifecycle:

- **platform/** — OS-specific credential storage (Keychain, Credential Manager, Secret Service)
- **auth/** — Three-hop token exchange with Microsoft Entra
- **audit/** — Action tracking — every resource access emits an audit event before executing
- **teams/** — Teams messaging via Graph API as the Agent User identity

## Build and Test (TDD)

This project uses test-driven development. All new code requires a failing test before implementation.

```bash
# Run all tests
pytest -v

# Run with coverage (80% threshold enforced)
pytest -v --cov=openclaw --cov-report=term-missing --cov-fail-under=80

# Single test
pytest tests/tools/test_teams.py::TestAcquireAgentUserToken::test_success -v

# Lint + format
ruff check . && ruff format .
```

Current status: **64 tests passing, 87% coverage**.

## Repository Map

| Directory | Purpose |
|-----------|---------|
| `src/openclaw/` | Application source code (18 modules) |
| `tests/` | Test suite (mirrors `src/` structure) |
| `scripts/` | Setup, teardown, and Entra provisioning scripts |
| `docs/` | Documentation site (MkDocs Material) |
| `docs/platform-learnings/` | Deep research on all integration platforms |
| `docs/decisions/` | Architecture Decision Records |
| `.github/` | CI workflows and Copilot instructions |

## Documentation

```bash
pip install mkdocs-material
mkdocs serve
```

Open http://localhost:8000 — or see [docs/index.md](docs/index.md) for a reading guide.

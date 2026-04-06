# System Overview

## Goal

Give device-local AI agents their own identity in Microsoft Entra so that every action is attributed to the agent, not the human. The agent authenticates autonomously as an **Agent User** — a purpose-built Entra user account with its own Teams presence, mailbox, and M365 license.

## Identity Hierarchy

```
Agent Identity Blueprint (application — one per project)
  └─ BlueprintPrincipal (service principal — must be created explicitly)
      └─ Agent Identity (service principal — one per device)
          └─ Agent User (user object — optional, 1:1, has Teams/mailbox)
```

## Authentication: Three-Hop Flow

No human in the loop. No device-code flow. No OBO. Fully autonomous:

```
Hop 1: Blueprint authenticates with client_secret
       → Blueprint token (client_credentials grant)

Hop 2: Agent Identity authenticates with Blueprint token as assertion
       → Agent Identity token (FIC exchange, client_credentials grant)

Hop 3: Agent User token via user_fic grant
       → Delegated token with idtyp=user
       → Can call Teams, Exchange, OneDrive, etc.
```

## System Topology

```
┌─────────────────────────────────────────────────────────┐
│  Local Device (Mac / Windows / Linux)                   │
│                                                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐          │
│  │ Platform │───▶│   Auth   │───▶│  Audit   │          │
│  │ (OS shim)│    │(3-hop)   │    │(log/emit)│          │
│  └──────────┘    └────┬─────┘    └──────────┘          │
│                       │                                 │
│                       ▼                                 │
│                 ┌──────────┐                            │
│                 │  Teams   │                            │
│                 │(Agent UX)│                            │
│                 └──────────┘                            │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
     ┌───────────────┐       ┌──────────────┐
     │ Microsoft     │       │ Microsoft    │
     │ Entra ID      │       │ Teams        │
     │ (Agent IDs,   │       │ (Graph API,  │
     │  Agent Users) │       │  Agent User) │
     └───────────────┘       └──────────────┘
```

## Four Core Modules

| Module | Purpose | Location |
|--------|---------|----------|
| **`platform/`** | OS-specific credential storage (Keychain, Credential Manager, Secret Service) | `src/openclaw/platform/` |
| **`auth/`** | Three-hop token exchange, Agent ID registration | `src/openclaw/auth/` |
| **`audit/`** | Action tracking — every resource access emits an audit event before executing | `src/openclaw/audit/` |
| **`teams/`** | Teams messaging via Graph API as the Agent User identity | `src/openclaw/teams/` |

## Provisioning

Setup is handled by two Python scripts called from `setup.sh`:

1. **`entra_provisioning.py`** — Creates/manages the dedicated provisioner app (client_credentials, avoids Azure CLI token rejection)
2. **`create_entra_agent_ids.py`** — Creates Blueprint, BlueprintPrincipal, Agent Identity, Agent User, and grants consent

State persists in `.openclaw-state.json` so re-runs are idempotent and don't reset secrets.

## Testing

TDD is a non-negotiable. All new code requires a failing test before implementation.

- 64 tests, 87% coverage (80% threshold enforced)
- Token flows tested with mocked `httpx` (via `respx`)
- Graph API calls tested with mocked HTTP responses
- Coverage omits: MCP entry point, logging config, OS-specific platform modules

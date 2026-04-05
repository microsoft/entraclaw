# System Overview

## Topology

Openclaw runs entirely on the local device. There is no hosted service — the agent, identity provider, and audit emitter all operate within the user's OS session. External dependencies are Microsoft Entra (for Agent ID issuance and OBO token exchange) and Microsoft Teams (for bidirectional human-agent communication).

```
┌─────────────────────────────────────────────────────┐
│  Local Device (Mac / Linux / Windows)               │
│                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐       │
│  │ Platform │───▶│   Auth   │───▶│  Audit   │       │
│  │ (OS shim)│    │(OBO/AgID)│    │(log/emit)│       │
│  └──────────┘    └────┬─────┘    └──────────┘       │
│                       │                             │
│                       ▼                             │
│                 ┌──────────┐                        │
│                 │  Teams   │                        │
│                 │(Agent UI)│                        │
│                 └──────────┘                        │
└────────────┬────────────────────────────────────────┘
             │
             ▼
     ┌───────────────┐       ┌──────────────┐
     │ Microsoft     │       │ Microsoft    │
     │ Entra ID      │       │ Teams        │
     │ (Agent IDs,   │       │ (Graph API,  │
     │  OBO tokens)  │       │  Agent User) │
     └───────────────┘       └──────────────┘
```

## Major Components

| Component | Role | Location |
|-----------|------|----------|
| `platform/` | OS-specific agent identity lifecycle — creation, keychain access, process isolation | `src/openclaw/platform/` |
| `auth/` | OBO token exchange, Agent ID registration, user consent prompts | `src/openclaw/auth/` |
| `audit/` | Action tracking — every agent resource access emits an audit event | `src/openclaw/audit/` |
| `teams/` | Bidirectional Teams integration — agent sends messages, human steers back | `src/openclaw/teams/` |

## Request Paths

### Happy path: Agent gets OBO token and does work

1. Agent starts on the device and requests an **Agent ID** via `platform/`
2. Agent prompts the human for **consent** to act on their behalf
3. Human approves → `auth/` performs an **OBO token exchange** with Entra
4. Agent receives a scoped token attributed to the Agent ID (not the human)
5. Agent performs work — every resource access goes through `audit/` first
6. Sign-in and access logs show the **agent** as the actor

### Teams communication path

1. Agent connects to Teams as an **Agent User** using its token
2. Agent sends status/results to the human via Teams messages
3. Human sends commands back through the same Teams channel
4. Agent receives and executes — analogous to `gh copilot --remote`

# Openclaw Identity Research — Engineering Summary

**Date:** April 6, 2026
**Team:** Brandon Werner
**Status:** MCP server built, Agent User auth flow implemented, setup script complete (8 steps), 64 tests passing (87% coverage)

---

## What We're Building

A proof-of-concept demonstrating that **device-local AI agents can have their own identity** in Microsoft Entra, separate from the human user. The agent gets an Agent Identity + Agent User, authenticates autonomously via the three-hop token flow, and interacts with Teams as its own digital worker.

**Identity Chain:** Blueprint (client_credentials) → Agent Identity (FIC exchange) → Agent User (user_fic grant) → Graph API with `idtyp=user` token

### The Demo Scenario

| Step | What Happens | What It Proves |
|------|-------------|----------------|
| 1. `./scripts/setup.sh` | Creates Provisioner, Blueprint, Agent Identity, Agent User | Proper Entra Agent ID provisioning works on device |
| 2. Assign M365 license | Agent User gets Teams/mailbox provisioning | Agent User is a real digital worker |
| 3. `copilot` (with Openclaw MCP) | MCP server starts, acquires Agent User token via three-hop flow | Agent authenticates autonomously — no human token needed |
| 4. `openclaw_teams_send` | Agent sends message to human in Teams as its own identity | Agent has working Teams integration |
| 5. Check Entra sign-in logs | Token shows agent identity, not human | **Identity attribution works** — the research goal |

### MCP Tools (4 total)

| Tool | Purpose | Status |
|------|---------|--------|
| `openclaw_whoami` | Show agent identity, sponsor, scopes | Built + tested |
| `openclaw_teams_send` | Send message to human in Teams | Built + tested |
| `openclaw_teams_read` | Read human's replies from Teams | Built + tested |
| `openclaw_audit_log` | Record audit event (action, resource, outcome) | Built + tested |

---

## TDD Status

```
64 passed in 0.32s

Coverage: 87% (threshold: 80%)

Name                                Stmts   Miss  Cover
--------------------------------------------------------
src/openclaw/config.py                 43     11    74%
src/openclaw/errors.py                 18      0   100%
src/openclaw/models.py                 47      0   100%
src/openclaw/platform/__init__.py      16     11    31%
src/openclaw/platform/base.py           9      3    67%
src/openclaw/tools/audit.py            26      5    81%
src/openclaw/tools/identity.py          7      0   100%
src/openclaw/tools/teams.py            79      3    96%
--------------------------------------------------------
TOTAL                                 245     33    87%
```

Omitted from coverage (untestable on a single platform):
- `mcp_server.py` (MCP integration entry point)
- `logging_config.py`
- `platform/mac.py`, `platform/linux.py`, `platform/windows.py` (OS-specific keyring)

---

## Current State

### What Works
- 1,067 lines of tests (64 tests, all passing, 87% coverage)
- 2,419 lines of application + provisioning code across 18 Python modules
- 490 lines of setup/teardown scripts (8-step setup, idempotent)
- Three-hop Agent User token flow (Blueprint → Agent Identity → Agent User)
- Agent User creation via Graph beta API (`microsoft.graph.agentUser`)
- Consent grant (`oAuth2PermissionGrant`) for Teams/Chat permissions
- Dedicated Provisioner app (avoids Azure CLI's `Directory.AccessAsUser.All` rejection)
- Provisioner state persisted in `.openclaw-state.json` (no secret reset on re-runs)
- Teams Graph API integration (send, read, connect) tested with mocked httpx
- Cross-platform credential storage (Keychain on Mac, Credential Manager on Windows)
- Structured JSON audit logging
- All code passes ruff lint + format

### What's In Progress
- End-to-end test: setup.sh → license assignment → MCP server → Teams message
- Verify Agent User token `idtyp=user` claim in Entra sign-in logs

### What's Not Started
- Windows VM provisioning and testing
- AppContainer sandbox spike
- Token auto-refresh (P1 TODO)
- Graph API rate limit handler (P2 TODO)

---

## Architecture

```
Blueprint (client_credentials)
  → Agent Identity (FIC exchange)
    → Agent User (user_fic grant, idtyp=user)
      → Graph API: Teams, Mail, OneDrive

┌─────────────────────────────────────────────────────────┐
│  Local Device (Mac / Windows)                           │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │ Copilot CLI (MCP Client)                         │   │
│  │   └── connects via stdio ──┐                     │   │
│  └────────────────────────────┼─────────────────────┘   │
│                               │                         │
│                               ▼                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │ Openclaw MCP Server (Python)                     │   │
│  │                                                  │   │
│  │  openclaw_whoami ──────▶ cached state            │   │
│  │  openclaw_teams_send ──▶ Graph API (Agent User)  │   │
│  │  openclaw_teams_read ──▶ Graph API (Agent User)  │   │
│  │  openclaw_audit_log ───▶ ~/.openclaw/audit/      │   │
│  │                                                  │   │
│  │  Token: Agent User (three-hop, idtyp=user)       │   │
│  └──────────────────────────────────────────────────┘   │
└───────────┬──────────────────────────┬──────────────────┘
            │                          │
            ▼                          ▼
    ┌───────────────┐          ┌──────────────┐
    │ Entra ID      │          │ Graph API    │
    │ Agent IDs     │          │ Teams Chat   │
    │ Agent Users   │          │ Messaging    │
    └───────────────┘          └──────────────┘
```

---

## Key Architectural Decisions

1. **Agent User over OBO** (ADR-002) — OBO required a human device-code flow and refresh token caching. Agent Users authenticate autonomously via the three-hop flow. No human in the loop.
2. **Dedicated provisioner app** — Azure CLI tokens include `Directory.AccessAsUser.All` which Agent Identity APIs reject. The provisioner uses `client_credentials` via `ClientSecretCredential`.
3. **Python provisioning scripts** (from agent-foundry-poc pattern) — `entra_provisioning.py` + `create_entra_agent_ids.py` replace the 823-line monolithic bash script.
4. **TDD** — Tests are written before implementation. Coverage enforced at 80% (currently 87%).

---

## Bugs Encountered & Resolved

### Bug 1: Azure CLI Tokens Rejected by Agent Identity APIs
**Impact:** Critical — setup failed with 403
**Fix:** Dedicated provisioner app with `client_credentials` flow.

### Bug 2: BlueprintPrincipal Not Auto-Created
**Impact:** Critical — Agent Identity creation failed with 400
**Fix:** Explicit `POST /servicePrincipals` with `AgentIdentityBlueprintPrincipal` type.

### Bug 3: Fake User Account Instead of Agent ID
**Impact:** Critical — fundamentally wrong identity model
**Fix:** Complete rewrite to Agent Identity Blueprint → Agent Identity → Agent User.

### Bug 4: OBO Was Unnecessary
**Impact:** Architectural — entire OBO chain was unnecessary complexity
**Fix:** Replaced with Agent User three-hop flow. Removed device-code flow, MSAL runtime dependency, human refresh token caching, access_as_user scope.

### Bug 5: Silent Script Failures
**Impact:** High — `2>/dev/null` and `source .env` under `set -e` hid errors
**Fix:** Removed all stderr swallowing. Guard `source` with `[ -f ]` check.

### Bug 6: Permission Propagation Delay
**Impact:** Medium — intermittent 403 on token acquisition
**Fix:** 10-40s backoff + 30s explicit propagation wait.

---

## Next Steps

1. **Run setup.sh end-to-end** — all 8 steps should work with the new provisioning scripts
2. **Assign M365 license** to Agent User and wait for Teams provisioning
3. **Test in Copilot CLI** — verify MCP tools work, Teams message appears as Agent User
4. **Check Entra sign-in logs** — confirm `idtyp=user` and agent identity attribution
5. **Provision Windows VM** — verify cross-platform setup
6. **Token auto-refresh** — handle 60-90 min token expiry gracefully

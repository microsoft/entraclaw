# Auth & Token Flows Layer

## Purpose

Handles all interactions with Microsoft Entra ID — Agent ID registration, OBO token exchange, consent management, and token lifecycle (refresh, revocation).

## Flows

### 1. Agent ID Registration

The agent registers itself with Entra to get a unique Agent ID. This is a one-time operation per agent instance.

### 2. On-Behalf-Of (OBO) Token Exchange

The core flow. The human user's token is exchanged for an agent-attributed token:

```
Human token (from device session)
        │
        ▼
┌──────────────────┐
│ MSAL OBO request │  assertion = human_token
│ to Entra         │  scope = requested_resources
└────────┬─────────┘
         │
         ▼
Agent token (attributed to Agent ID, acting on behalf of human)
```

The resulting token shows the **agent** as the actor in sign-in logs, with a reference back to the consenting human.

### 3. Device Code Flow (Bootstrap)

For initial human sign-in when no interactive browser is available (e.g., headless Linux), the device code flow provides a code the user enters in a browser.

### 4. Client Credentials (Agent-Only)

For operations where the agent acts under its own identity without human delegation. Limited scope — only for agent-to-agent or agent-to-infrastructure calls.

## Key Rule

**Never mix flow logic in a single function.** Each flow type gets its own module: `obo.py`, `device_code.py`, `client_credentials.py`.

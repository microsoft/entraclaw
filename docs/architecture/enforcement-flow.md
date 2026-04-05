# Enforcement Flow

## Overview

Every agent action that touches a resource must pass through the enforcement pipeline. This is not optional — the audit layer wraps resource access, not the other way around.

## Flow

```
Agent wants to access a resource
        │
        ▼
┌─────────────────┐
│ 1. Token check  │  Does the agent have a valid OBO token?
│    (auth/)      │  If expired → re-consent or refresh
└────────┬────────┘
         │ valid token
         ▼
┌─────────────────┐
│ 2. Audit emit   │  Log the intent BEFORE the action
│    (audit/)     │  Event: agent_id, resource, action, timestamp
└────────┬────────┘
         │ event recorded
         ▼
┌─────────────────┐
│ 3. Execute      │  Perform the actual resource access
│    (caller)     │  Using the OBO token
└────────┬────────┘
         │ result
         ▼
┌─────────────────┐
│ 4. Audit result │  Log success/failure of the action
│    (audit/)     │  Append outcome to the audit event
└─────────────────┘
```

## Key Invariant

**Audit before execute.** If the audit emit fails, the action does not proceed. This ensures there is no "dark" agent activity — every attempted access is recorded, even if it ultimately fails.

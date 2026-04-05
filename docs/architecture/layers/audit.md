# Audit Layer

## Purpose

Every agent action that touches a resource must emit an audit event. The audit layer is the enforcement boundary — if audit fails, the action does not proceed.

## Design Principles

1. **Audit before execute** — the event is recorded before the action is attempted
2. **Append-only** — audit events are never modified or deleted
3. **Structured events** — all events use typed models, never raw dicts
4. **Agent attribution** — every event includes the Agent ID, not just the human user

## Event Schema

```python
@dataclass
class AuditEvent:
    event_id: str
    timestamp: datetime
    agent_id: str
    human_user_id: str
    action: str           # e.g., "file.read", "api.call", "teams.send"
    resource: str         # what was accessed
    outcome: str          # "pending", "success", "failure"
    metadata: dict        # action-specific details (redacted of secrets)
```

## Open Question: Universal Audit Store

How do you track agent actions across Mac, Linux, and Windows with a single queryable store?

Options under investigation:
- Local SQLite per device + periodic sync to a central store
- OS-native event logs (Unified Logging on macOS, journald on Linux, ETW on Windows) with a collector
- Direct write to a cloud audit service (Azure Monitor, Application Insights)

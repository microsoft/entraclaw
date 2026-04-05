# Teams Integration Layer

## Purpose

Enables bidirectional communication between the agent and the human user through Microsoft Teams. The agent connects as an "Agent User" — it can send messages to the human and receive commands back.

## Communication Model

```
┌──────────────┐        Teams Channel        ┌──────────────┐
│              │  ──── status/results ────▶   │              │
│    Agent     │                              │    Human     │
│  (local)     │  ◀──── commands ────────     │  (Teams)     │
│              │                              │              │
└──────────────┘                              └──────────────┘
```

This is analogous to `gh copilot --remote` — steering a local agent session through a remote UI.

## Identity Challenge

The agent needs a Teams-compatible identity. Current options:

| Option | Pros | Cons |
|--------|------|------|
| Live ID | Existing infra | Nearly deprecated, doesn't scale |
| Entra Agent ID as Teams user | Aligned with project goals | Teams Graph API support unclear |
| Bot Framework registration | Well-supported | Different identity model, not OBO |

**Open question:** Which identity path lets the agent appear in Teams as a distinct "Agent User" while using the same OBO token chain?

## Graph API Dependencies

The agent interacts with Teams via the Microsoft Graph API. Any gaps between what the Graph API supports and what the Teams UX can do should be documented and reported — Office is obligated to close those gaps within 30 days.
